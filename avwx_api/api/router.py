"""Flight path routing API endpoints."""

from contextlib import suppress
from typing import ClassVar

from avwx import Station
from avwx.exceptions import BadStation
from avwx.structs import Coord
from avwx_api_core.services import FlightRouter, InvalidRequest
from avwx_api_core.token import Token
from quart import Response
from quart_openapi.cors import crossdomain
from shapely.geometry import LineString, Polygon

import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import HEADERS, Base, parse_params, token_check
from avwx_api.handle.notam import NotamHandler
from avwx_api.service import FaaDinsNotam, FaaNotam
from avwx_api.station_manager import station_data_for

ROUTE_HANDLERS = {
    "metar": handle.MetarHandler(),
    "taf": handle.TafHandler(),
}


@app.route("/api/path/station")
class StationsAlong(Base):
    """Returns stations along a flight path"""

    validator = validate.station_along
    struct = structs.StationRoute
    example = "stations_along"
    plan_types = ("enterprise",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns reports along a flight path"""
        print(params)
        stations = await FlightRouter().fetch("station", params.distance, params.route)
        parsed = []
        for code in stations:
            with suppress(BadStation):
                station = Station.from_code(code)
                parsed.append(await station_data_for(station, token=token))
        resp = {
            "meta": handle.MetarHandler().make_meta(),
            "route": params.route,
            "results": parsed,
        }
        return self.make_response(resp, params)


@app.route("/api/path/airsigmet")
class AirSigAlong(Base):
    """Returns AirSigmets that intersect a flight path"""

    validator = validate.airsig_along
    struct = structs.AirSigRoute
    example = "airsig_along"
    plan_types = ("enterprise",)

    @staticmethod
    def _filter_intersects(route: list[Coord], reports: list[dict]) -> list[dict]:
        """Filters report list that intersect a flight path"""
        ret = []
        path = LineString(c.pair for c in route)
        for report in reports:
            for period in ("observation", "forecast"):
                with suppress(TypeError):
                    coords = report[period]["coords"]
                    if len(coords) < 3:
                        continue
                    poly = Polygon((c["lat"], c["lon"]) for c in coords)
                    if poly.intersects(path):
                        ret.append(report)
                        break
        return ret

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns reports along a flight path"""
        config = structs.ParseConfig.from_params(params, token)
        data, code = await handle.AirSigHandler().fetch_reports(config)
        if code != 200:
            return self.make_response(data, params, code)
        resp = {
            "meta": handle.MetarHandler().make_meta(),
            "route": params.route,
            "reports": self._filter_intersects(params.route, data["reports"]),
        }
        return self.make_response(resp, params)


@app.route("/api/path/notam")
class NotamAlong(Base):
    """Returns NOTAMs along a flight path"""

    validator = validate.notam_along
    struct = structs.NotamRoute
    handler = NotamHandler()
    key_remv = ("remarks",)
    example = "notam_along"
    plan_types = ("enterprise",)

    @staticmethod
    def check_intl_code(route: list[str]) -> bool:
        """Check for non-US ICAO codes and validate route."""
        has_intl = False
        for code in route:
            if not code.startswith("K"):
                has_intl = True
            if has_intl and len(code) != 4:
                msg = "Pathing for non-US NOTAMs only supports 4-letter ICAO codes"
                raise InvalidRequest(msg)
        if has_intl and not 1 < len(route) < 6:
            msg = "Pathing for non-US NOTAMs must have between 2 and 5 waypoints"
            raise InvalidRequest(msg)
        return has_intl

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns reports along a flight path"""
        config = structs.ParseConfig.from_params(params, token)
        try:
            service = FaaDinsNotam if self.check_intl_code(params.route) else FaaNotam
            reports = await service("notam").async_fetch(path=params.route)
        except InvalidRequest as exc:
            error_resp = {"error": f"Search criteria appears to be invalid: {exc.args[0]}"}
            return self.make_response(error_resp, params, 400)
        parsed = []
        for report in reports:
            data, code = await self.handler.parse_given(report, config)
            if code != 200:
                continue
            del data["meta"]
            parsed.append(data)
        resp = {
            "meta": self.handler.make_meta(),
            "route": params.route,
            "results": parsed,
        }
        return self.make_response(resp, params)


@app.route("/api/path/<report_type>")
class ReportsAlong(Base):
    """Returns reports along a flight path"""

    validator = validate.report_along
    struct = structs.ReportRoute
    handlers = ROUTE_HANDLERS
    key_repl: ClassVar[dict[str, str]] = {"base": "altitude"}
    key_remv = ("top",)
    example = "metar_along"
    plan_types = ("enterprise",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns reports along a flight path"""
        report_type = params.report_type
        config = structs.ParseConfig.from_params(params, token)
        try:
            reports = await FlightRouter().fetch(report_type, params.distance, params.route)
        except InvalidRequest:
            error_resp = {"error": f"Routing doesn't support {report_type}"}
            return self.make_response(error_resp, params, 400)
        handler = self.handlers[report_type]
        parsed, stations = [], []
        for report in reports:
            data, code = await handler.parse_given(report, config)
            if code != 200:
                continue
            del data["meta"]
            parsed.append(data)
            stations.append(data["station"])
        if parsed:
            # This is disabled since the data here doesn't conform to the mongo schema
            # await app.cache.update_many(report_type, stations, parsed)
            await app.station.add_many(stations, f"{report_type}-route")
        resp = {
            "meta": handler.make_meta(),
            "route": params.route,
            "results": parsed,
        }
        return self.make_response(resp, params)
