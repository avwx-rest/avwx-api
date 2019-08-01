"""
Michael duPont - michael@mdupont.com
avwx_api.api.station - Station API endpoints
"""

# stdlib
from dataclasses import asdict

# library
import avwx
from quart import Response
from quart_openapi.cors import crossdomain

# module
from avwx_api import app, counter, structs, validators
from avwx_api.api import Base, check_params, token_flag


@app.route("/api/station/<station>")
class Station(Base):
    """
    Returns station details for ICAO and coordinates
    """

    validator = validators.station
    struct = structs.StationParams
    report_type = "station"

    @crossdomain(origin="*")
    @check_params
    async def get(self, params: structs.Params) -> Response:
        """
        Returns raw station info if available
        """
        counter.increment_station(params.station.icao, "station")
        return self.make_response(asdict(params.station), params.format)


@app.route("/api/station/near/<coord>")
class Near(Base):
    """
    Returns stations near a coordinate pair
    """

    validator = validators.coord_search
    struct = structs.CoordSearchParams
    report_type = "station"
    loc_param = "coord"
    example = "stations_near"

    @crossdomain(origin="*")
    @check_params
    @token_flag
    async def get(self, params: structs.Params) -> Response:
        """
        Returns raw station info if available
        """
        lat, lon = params.coord
        n, reporting, dist = params.n, params.reporting, params.maxdist
        stations = avwx.station.nearest(lat, lon, n, reporting, dist)
        if isinstance(stations, tuple):
            stations = [stations]
        data = [{"distance": d, "station": asdict(s)} for s, d in stations]
        return self.make_response(data, params.format)
