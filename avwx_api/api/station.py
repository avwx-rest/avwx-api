"""
Station API endpoints
"""

# stdlib
from typing import Optional

# library
from quart import Response
from quart_openapi.cors import crossdomain

# module
import avwx
from avwx_api_core.token import Token
from avwx_api import app, structs, validate
from avwx_api.api.base import Base, HEADERS, parse_params, token_check
from avwx_api.station_manager import station_data_for


async def get_station(station: avwx.Station, token: Optional[Token]) -> dict:
    """Log and returns station data as dict"""
    await app.station.add(station.icao, "station")
    return await station_data_for(station, token=token)


@app.route("/api/station/list")
class StationList(Base):
    """Returns the current list of reporting stations"""

    @crossdomain(origin="*", headers=HEADERS)
    @token_check
    async def get(self) -> Response:
        """Returns the current list of reporting stations"""
        return self.make_response(avwx.station.station_list())


@app.route("/api/station/<station>")
class Station(Base):
    """Returns station details for ICAO and coordinates"""

    validator = validate.station
    struct = structs.Station
    report_type = "station"

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns station details for ICAO and coordinates"""
        data = await get_station(params.station, token)
        return self.make_response(data, params.format)


@app.route("/api/multi/station/<stations>")
class MultiStation(Base):
    """Returns station details for multiple ICAO idents"""

    validator = validate.stations
    struct = structs.Stations
    report_type = "station"
    example = "multi_station"
    loc_param = "stations"
    plan_types = ("pro", "enterprise")

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params, token: Optional[Token]) -> Response:
        """Returns station details for multiple ICAO idents"""
        data = {s.icao: await get_station(s, token) for s in params.stations}
        return self.make_response(data, params.format)
