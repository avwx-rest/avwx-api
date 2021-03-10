"""
Michael duPont - michael@mdupont.com
avwx_api.api.station - Station API endpoints
"""

# stdlib
from dataclasses import asdict
from typing import Optional

# library
from quart import Response
from quart_openapi.cors import crossdomain

# module
import avwx
from avwx_api_core.token import Token
from avwx_api import app, structs, validate
from avwx_api.api.base import Base, HEADERS, parse_params, token_check


async def get_station(station: avwx.Station) -> dict:
    """Log and returns station data as dict"""
    await app.station.add(station.icao, "station")
    return asdict(station)


@app.route("/api/station/<station>")
class Station(Base):
    """Returns station details for ICAO and coordinates"""

    validator = validate.station
    struct = structs.StationParams
    report_type = "station"

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """Returns station details for ICAO and coordinates"""
        data = await get_station(params.station)
        return self.make_response(data, params.format)


@app.route("/api/multi/station/<stations>")
class MultiStation(Base):
    """Returns station details for multiple ICAO idents"""

    validator = validate.stations
    struct = structs.StationsParams
    report_type = "station"
    example = "multi_station"
    loc_param = "stations"
    plan_types = ("pro", "enterprise")

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """Returns station details for multiple ICAO idents"""
        data = {s.icao: await get_station(s) for s in params.stations}
        return self.make_response(data, params.format)


@app.route("/api/station/near/<coord>")
class Near(Base):
    """Returns stations near a coordinate pair"""

    validator = validate.coord_search
    struct = structs.CoordSearchParams
    report_type = "station"
    loc_param = "coord"
    example = "stations_near"
    param_plans = ("pro", "enterprise")
    include_token = True

    def valid_token(self, token: Optional[Token]) -> bool:
        """Returns True if token can use special param values"""
        if token is None:
            return False
        return not (token.is_developer or token.valid_type(self.param_plans))

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(
        self, params: structs.Params, token: Optional[Token] = None
    ) -> Response:
        """Returns stations near a coordinate pair"""
        if params.n > 10 and self.valid_token(token):
            data = {
                "error": "n is greater than 10 for free account",
                "param": "n",
                "help": validate.HELP.get("n"),
            }
            return self.make_response(data, code=400)
        stations = avwx.station.nearest(
            *params.coord, params.n, params.airport, params.reporting, params.maxdist
        )
        if isinstance(stations, dict):
            stations = [stations]
        for i, stn in enumerate(stations):
            stations[i]["station"] = asdict(stn["station"])
        return self.make_response(stations, params.format)


@app.route("/api/station/search")
class TextSearch(Base):
    """Returns stations from a text-based search"""

    validator = validate.text_search
    struct = structs.TextSearchParams
    report_type = "station"
    example = "station_search"
    param_plans = ("pro", "enterprise")
    include_token = True

    def valid_token(self, token: Optional[Token]) -> bool:
        """Returns True if token can use special param values"""
        if token is None:
            return False
        return not (token.is_developer or token.valid_type(self.param_plans))

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(
        self, params: structs.Params, token: Optional[Token] = None
    ) -> Response:
        """Returns stations from a text-based search"""
        if params.n > 10 and self.valid_token(token):
            data = {
                "error": "n is greater than 10 for free account",
                "param": "n",
                "help": validate.HELP.get("n"),
            }
            return self.make_response(data, code=400)
        stations = avwx.station.search(
            params.text, params.n, params.airport, params.reporting
        )
        stations = [asdict(s) for s in stations]
        return self.make_response(stations, params.format)


@app.route("/api/station/list")
class StationList(Base):
    """Returns the current list of reporting stations"""

    @crossdomain(origin="*", headers=HEADERS)
    @token_check
    async def get(self) -> Response:
        """Returns the current list of reporting stations"""
        return self.make_response(avwx.station.station_list())
