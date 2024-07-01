"""Functional API endpoints separate from static views."""

# stdlib
import json
import asyncio as aio
from functools import wraps
from pathlib import Path
from typing import Optional

# library
from quart import Response, request
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid

# module
import avwx
from avwx_api_core.views import AuthView, Token, make_token_check
from avwx_api import app, structs, validate
from avwx_api.handle.base import ManagerHandler, ReportHandler


HEADERS = ["Authorization", "Content-Type"]


EXAMPLE_PATH = Path(__file__).parent / "examples"


def parse_params(func):
    """Collect and parses endpoint parameters."""

    @wraps(func)
    async def wrapper(self, **kwargs):
        keys = ("report_type", self.loc_param)
        params = {key: kwargs.get(key) for key in keys}
        params = self.validate_params(**params)
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        return await func(self, params)

    return wrapper


token_check = make_token_check(app)


class Base(AuthView):
    """Base report endpoint"""

    validator: validate.Schema
    struct: structs.Params
    report_type: str | None = None
    handler: ReportHandler | None = None
    handlers: dict[str, ReportHandler] = None

    # Name of parameter used for report location
    loc_param: str = "station"

    def __init__(self):
        super().__init__()
        if self.handler:
            self.handler = self.handler()
            self.report_type = self.handler.report_type
        if self.handlers:
            self.handlers = {k: v() for k, v in self.handlers.items()}

    def validate_params(self, **kwargs) -> structs.Params:
        """Returns all validated request parameters or an error response dict"""
        try:
            params = {**request.args, **kwargs}
            if not params.get("report_type"):
                params["report_type"] = self.report_type
            # Unpack param lists. Ex: options: ['info,speech'] -> options: 'info,speech'
            for key, val in params.items():
                if isinstance(val, list):
                    params[key] = val[0]
            return self.struct(**self.validator(params))
        except (Invalid, MultipleInvalid) as exc:
            key = str(exc.path[0])
            return {"error": str(exc.msg), "param": key, "help": validate.HELP.get(key)}

    def get_example_file(self, report_type: str) -> dict:
        """Load example payload from report type"""
        path = EXAMPLE_PATH / f"{self.example or report_type}.json"
        try:
            return {"sample": json.load(path.open())}
        except FileNotFoundError:
            return {}


class Report(Base):
    """Fetch Report Endpoint"""

    validator = validate.report_station
    struct = structs.ReportStation

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Report, token: Optional[Token]) -> Response:
        """GET handler returning reports"""
        config = structs.ParseConfig.from_params(params, token)
        await app.station.from_params(params, params.report_type)
        handler = self.handler or self.handlers.get(params.report_type)
        if isinstance(handler, ManagerHandler):
            fetch = handler.fetch_reports(config)
        elif isinstance(handler, ReportHandler):
            loc = getattr(params, self.loc_param, None)
            fetch = handler.fetch_report(loc, config)
        data, code = await fetch
        return self.make_response(data, params, code)


class Parse(Base):
    """Given report endpoint"""

    validator = validate.report_given
    struct = structs.ReportGiven

    @crossdomain(origin="*", headers=HEADERS)
    @token_check
    async def post(self, token: Optional[Token], **kwargs) -> Response:
        """POST handler to parse given reports"""
        data = await request.data
        params: structs.ReportGiven = self.validate_params(
            report=data.decode() or None, **kwargs
        )
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        config = structs.ParseConfig.from_params(params, token)
        handler = self.handler or self.handlers.get(params.report_type)
        data, code = await handler.parse_given(params.report, config)
        if "station" in data:
            report_type = f"{params.report_type}-given"
            await app.station.add(data["station"], report_type)
        return self.make_response(data, params, code)


class MultiReport(Base):
    """Multiple METAR and TAF reports in one endpoint"""

    validator = validate.report_stations
    struct = structs.ReportStations
    loc_param = "stations"
    plan_types = ("pro", "enterprise")

    # If True, returns a dict with station idents. Otherwise a list based on location order
    keyed: bool = True

    log_postfix = "multi"

    def get_locations(self, params: structs.Params) -> list[avwx.Station | dict]:
        """Returns the list of locations to pass to each handler"""
        return getattr(params, self.loc_param)

    @staticmethod
    def split_distances(data: list[avwx.Station | dict]) -> tuple[list, dict]:
        """Splits any distances from the location data"""
        locations, distances = [], {}
        for item in data:
            if isinstance(item, dict):
                station: avwx.Station = item.pop("station")
                locations.append(station)
                distances[station.storage_code] = item
            else:
                locations.append(item)
        return locations, distances

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Report, token: Optional[Token]) -> Response:
        """GET handler returning multiple reports"""
        locations, distances = self.split_distances(self.get_locations(params))
        config = structs.ParseConfig.from_params(params, token)
        handler = self.handler or self.handlers.get(params.report_type)

        coros = []
        for loc in locations:
            coros.append(handler.fetch_report(loc, config))
            await app.station.add(
                loc.storage_code, f"{params.report_type}-{self.log_postfix}"
            )
        data = [r[0] for r in await aio.gather(*coros)]

        # Expand to keyed dict when supplied specific keys
        if self.keyed:
            keys = [
                loc.storage_code if hasattr(loc, "storage_code") else loc
                for loc in locations
            ]
            data = dict(zip(keys, data))
        # Remove non-existing responses for list results
        else:
            data = [d for d in data if "error" not in d]

        # Add distances if included from locations
        if distances:
            for i, item in enumerate(data):
                data[i]["distance"] = distances.get(item.get("station"), {})

        return self.make_response(data, params)
