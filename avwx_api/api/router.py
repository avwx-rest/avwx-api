"""
Flight path routing API endpoints
"""

# stdlib
from contextlib import suppress
from typing import Optional

# library
from quart import Response
from quart_openapi.cors import crossdomain

# stdlib
from avwx import Station
from avwx.exceptions import BadStation
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
        config = structs.ParseConfig.from_params(params, token)
        stations = await FlightRouter().fetch("station", params.distance, params.route)
        resp = []
        for icao in stations:
            with suppress(BadStation):
                station = Station.from_icao(icao)
                resp.append(await station_data_for(station, config))
        resp = {
            "meta": handle.MetarHandler().make_meta(),
            "route": params.route,
            "results": resp,
        }
        return self.make_response(resp, params.format)


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
            return self.make_response(resp, params.format, 400)
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
        return self.make_response(resp, params.format)
