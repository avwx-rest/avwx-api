"""
Michael duPont - michael@mdupont.com
avwx_api.api - Functional API endpoints separate from static views
"""

# stdlib
import json
import asyncio as aio
from functools import wraps
from pathlib import Path

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
    async def wrapper(self, *args, **kwargs):
        loc = {self.loc_param: kwargs.get(self.loc_param)}
        params = self.validate_params(**loc)
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

    # Name of parameter used for report location
    loc_param: str = "station"

    def validate_params(self, **kwargs) -> structs.Params:
        """
        Returns all validated request parameters or an error response dict
        """
        try:
            params = {"report_type": self.report_type, **request.args, **kwargs}
            # Unpack param lists. Ex: options: ['info,speech'] -> options: 'info,speech'
            for k, v in params.items():
                if isinstance(v, list):
                    params[k] = v[0]
            return self.struct(**self.validator(params))
        except (Invalid, MultipleInvalid) as exc:
            key = exc.path[0]
            return {"error": str(exc.msg), "param": key, "help": validate.HELP.get(key)}

    def get_example_file(self) -> dict:
        """
        Load example payload from report type
        """
        path = EXAMPLE_PATH / f"{self.example or self.report_type}.json"
        return json.load(path.open())


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
        handler = getattr(handle, self.report_type).handle_report
        await app.station.from_params(params, self.report_type)
        data, code = await handler(loc, params.options, nofail)
        return self.make_response(data, params.format, code)


class Parse(Base):
    """
    Given report endpoint
    """

    validator = validate.report_given
    struct = structs.ReportGivenParams

    @crossdomain(origin="*", headers=HEADERS)
    @token_check
    async def post(self) -> Response:
        """
        POST handler to parse given reports
        """
        data = await request.data
        params = self.validate_params(report=data.decode() or None)
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        handler = getattr(handle, self.report_type).parse_given
        data, code = handler(params.report, params.options)
        if "station" in data:
            report_type = self.report_type + "-given"
            await app.station.add(data["station"], report_type)
        return self.make_response(data, params.format, code)


class MultiReport(Base):
    """
    Multiple METAR and TAF reports in one endpoint
    """

    validator = validate.report_stations
    struct = structs.ReportStationsParams
    loc_param = "stations"
    plan_types = ("paid",)

    @crossdomain(origin="*", headers=HEADERS)
    @parse_params
    @token_check
    async def get(self, params: structs.Params) -> Response:
        """
        GET handler returning multiple reports
        """
        locs = getattr(params, self.loc_param)
        nofail = params.onfail == "cache"
        handler = getattr(handle, self.report_type).handle_report
        coros = []
        for loc in locs:
            coros.append(handler(loc, params.options, nofail))
            await app.station.add(loc.icao, self.report_type + "-multi")
        results = await aio.gather(*coros)
        keys = [loc.icao if hasattr(loc, "icao") else loc for loc in locs]
        data = dict(zip(keys, [r[0] for r in results if r]))
        return self.make_response(data, params.format)


from avwx_api.api import metar, pirep, station, taf
