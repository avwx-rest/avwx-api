"""Station API endpoints."""

from typing import Any

import avwx
from avwx_api_core.token import Token
from quart import Response
from quart_openapi.cors import crossdomain

from avwx_api import app, structs, validate
from avwx_api.api.base import HEADERS, Base, parse_params, token_check
from avwx_api.station_manager import station_data_for


async def get_station(station: avwx.Station, token: Token | None) -> dict:
    """Log and returns station data as dict"""
    await app.station.add(station.storage_code, "station")
    return await station_data_for(station, token=token) or {}


@app.route("/api/station/list")
class StationList(Base):
    """Returns the current list of reporting stations"""

    validator = validate.station_list
    struct = structs.StationList

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, _: Any) -> Response:
        """Returns the current list of reporting stations"""
        data = avwx.station.station_list(reporting=params.reporting)
        return self.make_response(data, params)


@app.route("/api/station/<station>")
class Station(Base):
    """Returns station details for ident and coordinates"""

    validator = validate.station
    struct = structs.Station
    report_type = "station"

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns station details for idents and coordinates"""
        data = await get_station(params.station, token)
        return self.make_response(data, params)


@app.route("/api/multi/station/<stations>")
class MultiStation(Base):
    """Returns station details for multiple idents"""

    validator = validate.stations
    struct = structs.Stations
    report_type = "station"
    example = "multi_station"
    loc_param = "stations"
    plan_types = ("pro", "enterprise")

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Token | None) -> Response:
        """Returns station details for multiple idents"""
        data = {s.storage_code: await get_station(s, token) for s in params.stations}
        return self.make_response(data, params)
