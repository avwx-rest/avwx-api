"""
Functional API endpoints separate from static views
"""

# stdlib
import json
import asyncio as aio
from functools import wraps
from pathlib import Path
from typing import Dict

# library
from quart import Response, request
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid

# module
from avwx_api_core.views import AuthView, make_token_check
from avwx_api import app, handle, structs, validate


HEADERS = ["Authorization", "Content-Type"]


EXAMPLE_PATH = Path(__file__).parent / "examples"


def parse_params(func):
    """
    Collects and parses endpoint parameters
    """

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
    """
    Base report endpoint
    """

    validator: validate.Schema
    struct: structs.Params
    report_type: str = None
    handler: handle.base.ReportHandler = None
    handlers: Dict[str, handle.base.ReportHandler] = None

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
        """
        Returns all validated request parameters or an error response dict
        """
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
            key = exc.path[0]
            return {"error": str(exc.msg), "param": key, "help": validate.HELP.get(key)}

    def get_example_file(self, report_type: str) -> dict:
        """
        Load example payload from report type
        """
        path = EXAMPLE_PATH / f"{self.example or report_type}.json"
        return {"sample": json.load(path.open())}


class Report(Base):
    """
    Fetch Report Endpoint
    """

    validator = validate.report_station
    struct = structs.ReportStationParams

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """
        GET handler returning reports
        """
        nofail = params.onfail == "cache"
        loc = getattr(params, self.loc_param)
        await app.station.from_params(params, params.report_type)
        handler = self.handler or self.handlers.get(params.report_type)
        data, code = await handler.fetch_report(loc, params.options, nofail)
        return self.make_response(data, params.format, code)


class Parse(Base):
    """
    Given report endpoint
    """

    validator = validate.report_given
    struct = structs.ReportGivenParams

    @crossdomain(origin="*", headers=HEADERS)
    @token_check
    async def post(self, **kwargs) -> Response:
        """
        POST handler to parse given reports
        """
        data = await request.data
        params = self.validate_params(report=data.decode() or None, **kwargs)
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        handler = self.handler or self.handlers.get(params.report_type)
        data, code = handler.parse_given(params.report, params.options)
        if "station" in data:
            report_type = params.report_type + "-given"
            await app.station.add(data["station"], report_type)
        return self.make_response(data, params.format, code)


class MultiReport(Base):
    """
    Multiple METAR and TAF reports in one endpoint
    """

    validator = validate.report_stations
    struct = structs.ReportStationsParams
    loc_param = "stations"
    plan_types = ("pro", "enterprise")

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """
        GET handler returning multiple reports
        """
        locs = getattr(params, self.loc_param)
        nofail = params.onfail == "cache"
        handler = self.handler or self.handlers.get(params.report_type)
        coros = []
        for loc in locs:
            coros.append(handler.fetch_report(loc, params.options, nofail))
            await app.station.add(loc.icao, params.report_type + "-multi")
        results = await aio.gather(*coros)
        keys = [loc.icao if hasattr(loc, "icao") else loc for loc in locs]
        data = dict(zip(keys, [r[0] for r in results if r]))
        return self.make_response(data, params.format)
