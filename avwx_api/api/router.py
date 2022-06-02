"""
Flight path routing API endpoints
"""

# stdlib
from contextlib import suppress
from typing import Optional

# library
from quart import Response
from quart_openapi.cors import crossdomain
from shapely.geometry import LineString, Polygon

# module
from avwx import Station
from avwx.exceptions import BadStation
from avwx.service import FAA_NOTAM
from avwx.structs import Coord
from avwx_api_core.services import FlightRouter, InvalidRequest
from avwx_api_core.token import Token
import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import Base, HEADERS, parse_params, token_check
from avwx_api.station_manager import station_data_for


ROUTE_HANDLERS = {
    "metar": handle.MetarHandler,
    "taf": handle.TafHandler,
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
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns reports along a flight path"""
        stations = await FlightRouter().fetch("station", params.distance, params.route)
        resp = []
        for code in stations:
            with suppress(BadStation):
                station = Station.from_code(code)
                resp.append(await station_data_for(station, token=token))
        resp = {
            "meta": handle.MetarHandler().make_meta(),
            "route": params.route,
            "results": resp,
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
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
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
    handler = handle.NotamHandler
    key_remv = ("remarks",)
    example = "notam_along"
    plan_types = ("enterprise",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns reports along a flight path"""
        config = structs.ParseConfig.from_params(params, token)
        try:
            reports = await FAA_NOTAM("notam").async_fetch(path=params.route)
        except InvalidRequest:
            resp = {"error": "Search criteria appears to be invalid"}
            return self.make_response(resp, params, 400)
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
    key_repl = {"base": "altitude"}
    key_remv = ("top",)
    example = "metar_along"
    plan_types = ("enterprise",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns reports along a flight path"""
        report_type = params.report_type
        config = structs.ParseConfig.from_params(params, token)
        try:
            reports = await FlightRouter().fetch(
                report_type, params.distance, params.route
            )
        except InvalidRequest:
            resp = {"error": f"Routing doesn't support {report_type}"}
            return self.make_response(resp, params, 400)
        handler = self.handlers.get(report_type)
        resp, stations = [], []
        for report in reports:
            data, code = await handler.parse_given(report, config)
            if code != 200:
                continue
            del data["meta"]
            resp.append(data)
            stations.append(data["station"])
        await app.cache.update_many(report_type, stations, resp)
        await app.station.add_many(stations, report_type + "-route")
        resp = {
            "meta": handler.make_meta(),
            "route": params.route,
            "results": resp,
        }
        return self.make_response(resp, params)
