"""
Flight path routing API endpoints
"""

# library
from quart import Response
from quart_openapi.cors import crossdomain

# stdlib
import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import Base, HEADERS, parse_params, token_check
from avwx_api.services import FlightRouter, InvalidRequest


ROUTE_HANDLERS = {
    "metar": handle.MetarHandler,
    "taf": handle.TafHandler,
}


@app.route("/api/path/<report_type>")
class Along(Base):
    """Returns stations near a coordinate pair"""

    validator = validate.report_along
    struct = structs.FlightRoute
    handlers = ROUTE_HANDLERS
    example = "metar"
    plan_types = ("enterprise",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """Returns reports along a flight path"""
        report_type = params.report_type
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
            data, code = handler.parse_given(report, params.options)
            if code != 200:
                continue
            del data["meta"]
            resp.append(data)
            stations.append(data["station"])
        await app.cache.update_many(report_type, stations, resp)
        await app.station.add_many(stations, report_type + "-route")
        resp = {"meta": handler.make_meta(), "results": resp}
        return self.make_response(resp, params.format)
