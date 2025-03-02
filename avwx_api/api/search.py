"""Search API endpoints."""

from typing import Any, ClassVar

import avwx.station
from avwx_api_core.token import Token
from quart import Response
from quart_openapi.cors import crossdomain

import avwx_api.handle.current as handle
from avwx_api import app, structs, validate
from avwx_api.api.base import HEADERS, Base, MultiReport, parse_params, token_check
from avwx_api.station_manager import station_data_for

SEARCH_HANDLERS = {
    "metar": handle.MetarHandler(),
    "taf": handle.TafHandler(),
}

COUNT_MAX = 10
PAID_PLANS = ("pro", "enterprise")


def check_count_limit(count: int, token: Token | None, plans: tuple[str, ...]) -> dict | None:
    """Return an error payload if the count is greater than the user is allowed."""
    if count <= COUNT_MAX or token is None:
        return None
    if token.is_developer or token.valid_type(plans):
        return None
    return {
        "error": f"n is greater than {COUNT_MAX} for your account",
        "param": "n",
        "help": validate.HELP.get("n"),
    }


def arg_matching(target: Any, args: tuple[Any, ...]) -> Any:
    """Return the first arg matching the target type."""
    return next((arg for arg in args if isinstance(arg, target)), None)


@app.route("/api/station/near/<coord>")
class Near(Base):
    """Return stations near a coordinate pair."""

    validator = validate.coord_search
    struct = structs.CoordSearch
    loc_param = "coord"
    example = "stations_near"

    def validate_token_parameters(self, token: Token, *args: Any) -> dict | None:
        """Return an error payload if parameter validation doesn't match plan level."""
        params: structs.StationSearch = arg_matching(self.struct, args)
        return check_count_limit(params.n, token, PAID_PLANS)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.CoordSearch, token: Token | None) -> Response:
        """Return stations near a coordinate pair."""
        stations = avwx.station.nearest(
            params.coord.lat,
            params.coord.lon,
            params.n,
            is_airport=params.airport,
            sends_reports=params.reporting,
            max_coord_distance=params.maxdist,
        )
        if isinstance(stations, dict):
            stations = [stations]
        for i, stn in enumerate(stations):
            stations[i]["station"] = await station_data_for(stn["station"], token=token)
        return self.make_response(stations, params)


@app.route("/api/search/station")
class TextSearch(Base):
    """Return stations from a text-based search."""

    validator = validate.text_search
    struct = structs.TextSearch
    example = "station_search"

    def validate_token_parameters(self, token: Token, *args: Any) -> dict | None:
        """Return an error payload if parameter validation doesn't match plan level."""
        params: structs.StationSearch = arg_matching(self.struct, args)
        return check_count_limit(params.n, token, PAID_PLANS)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.TextSearch, token: Token | None) -> Response:
        """Return stations from a text-based search."""
        stations = avwx.station.search(params.text, params.n, is_airport=params.airport, sends_reports=params.reporting)
        stations = [await station_data_for(s, token=token) for s in stations]
        return self.make_response(stations, params)


@app.route("/api/<report_type>/near/<coord>")
class ReportCoordSearch(MultiReport):
    """Return reports nearest to a coordinate."""

    validator = validate.report_coord_search
    struct = structs.ReportCoordSearch
    handlers = SEARCH_HANDLERS
    key_repl: ClassVar[dict[str, str]] = {"base": "altitude"}
    key_remv = ("top",)
    plan_types = PAID_PLANS
    loc_param = "coord"
    keyed = False
    log_postfix = "coord"

    def validate_token_parameters(self, token: Token, *args: Any) -> dict | None:
        """Return an error payload if parameter validation doesn't match plan level."""
        params = arg_matching(self.struct, args)
        return check_count_limit(params.n, token, ("enterprise",))

    def get_locations(self, params: structs.CoordSearch) -> list[dict]:
        stations = avwx.station.nearest(
            params.coord.lat,
            params.coord.lon,
            params.n,
            is_airport=params.airport,
            sends_reports=params.reporting,
            max_coord_distance=params.maxdist,
        )
        if isinstance(stations, dict):
            stations = [stations]
        return stations


@app.route("/api/search/<report_type>")
class ReportTextSearch(MultiReport):
    """Return reports from a text-based search."""

    validator = validate.report_text_search
    struct = structs.ReportTextSearch
    handlers = SEARCH_HANDLERS
    key_repl: ClassVar[dict[str, str]] = {"base": "altitude"}
    key_remv = ("top",)
    plan_types = PAID_PLANS
    keyed = False
    log_postfix = "search"

    def validate_token_parameters(self, token: Token, *args: Any) -> dict | None:
        """Return an error payload if parameter validation doesn't match plan level."""
        params: structs.StationSearch = arg_matching(self.struct, args)
        return check_count_limit(params.n, token, ("enterprise",))

    def get_locations(self, params: structs.TextSearch) -> list[dict]:
        return avwx.station.search(
            params.text,
            params.n,
            is_airport=params.airport,
            sends_reports=params.reporting,
        )
