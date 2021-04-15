"""
Search API endpoints
"""

# pylint: disable=arguments-differ,too-many-ancestors

# stdlib
from dataclasses import asdict
from typing import Any, Optional

# library
from quart import Response
from quart_openapi.cors import crossdomain

# module
import avwx
from avwx_api_core.token import Token
import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import Base, HEADERS, MultiReport, parse_params, token_check


SEARCH_HANDLERS = {
    "metar": handle.MetarHandler,
    "taf": handle.TafHandler,
}

COUNT_MAX = 10
PAID_PLANS = ("pro", "enterprise")


def check_count_limit(
    count: int, token: Optional[Token], plans: tuple[str]
) -> Optional[dict]:
    """Returns an error payload if the count is greater than the user is allowed"""
    if count <= COUNT_MAX or token is None:
        return None
    if token.is_developer or token.valid_type(plans):
        return None
    return {
        "error": f"n is greater than {COUNT_MAX} for your account",
        "param": "n",
        "help": validate.HELP.get("n"),
    }


def arg_matching(target: Any, args: tuple[Any]) -> Any:
    """Returns the first arg matching the target type"""
    for arg in args:
        if isinstance(arg, target):
            return arg
    return None


@app.route("/api/station/near/<coord>")
class Near(Base):
    """Returns stations near a coordinate pair"""

    validator = validate.coord_search
    struct = structs.CoordSearch
    loc_param = "coord"
    example = "stations_near"

    def validate_token_parameters(self, token: Token, *args) -> Optional[dict]:
        """Returns an error payload if parameter validation doesn't match plan level"""
        params = arg_matching(self.struct, args)  # pylint: disable=no-member
        return check_count_limit(params.n, token, PAID_PLANS)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """Returns stations near a coordinate pair"""
        stations = avwx.station.nearest(
            *params.coord, params.n, params.airport, params.reporting, params.maxdist
        )
        if isinstance(stations, dict):
            stations = [stations]
        for i, stn in enumerate(stations):
            stations[i]["station"] = asdict(stn["station"])
        return self.make_response(stations, params.format)


@app.route("/api/search/station")
class TextSearch(Base):
    """Returns stations from a text-based search"""

    validator = validate.text_search
    struct = structs.TextSearch
    example = "station_search"

    def validate_token_parameters(self, token: Token, *args) -> Optional[dict]:
        """Returns an error payload if parameter validation doesn't match plan level"""
        params = arg_matching(self.struct, args)  # pylint: disable=no-member
        return check_count_limit(params.n, token, PAID_PLANS)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """Returns stations from a text-based search"""
        stations = avwx.station.search(
            params.text, params.n, params.airport, params.reporting
        )
        stations = [asdict(s) for s in stations]
        return self.make_response(stations, params.format)


@app.route("/api/<report_type>/near/<coord>")
class ReportCoordSearch(MultiReport):
    """Returns reports nearest to a coordinate"""

    validator = validate.report_coord_search
    struct = structs.ReportCoordSearch
    handlers = SEARCH_HANDLERS
    key_repl = {"base": "altitude"}
    key_remv = ("top",)
    plan_types = PAID_PLANS
    loc_param = "coord"
    keyed = False
    log_postfix = "coord"

    def validate_token_parameters(self, token: Token, *args) -> Optional[dict]:
        """Returns an error payload if parameter validation doesn't match plan level"""
        params = arg_matching(self.struct, args)  # pylint: disable=no-member
        return check_count_limit(params.n, token, ("enterprise",))

    def get_locations(self, params: structs.Params) -> list[dict]:
        stations = avwx.station.nearest(
            *params.coord, params.n, params.airport, params.reporting, params.maxdist
        )
        if isinstance(stations, dict):
            stations = [stations]
        return stations


@app.route("/api/search/<report_type>")
class ReportTextSearch(MultiReport):
    """Returns reports from a text-based search"""

    validator = validate.report_text_search
    struct = structs.ReportTextSearch
    handlers = SEARCH_HANDLERS
    key_repl = {"base": "altitude"}
    key_remv = ("top",)
    plan_types = PAID_PLANS
    keyed = False
    log_postfix = "search"

    def validate_token_parameters(self, token: Token, *args) -> Optional[dict]:
        """Returns an error payload if parameter validation doesn't match plan level"""
        params = arg_matching(self.struct, args)  # pylint: disable=no-member
        return check_count_limit(params.n, token, ("enterprise",))

    def get_locations(self, params: structs.Params) -> list[dict]:
        return avwx.station.search(
            params.text, params.n, params.airport, params.reporting
        )
