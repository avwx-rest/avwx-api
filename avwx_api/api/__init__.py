"""
Michael duPont - michael@mdupont.com
avwx_api.api - Functional API endpoints separate from static views
"""

# stdlib
import json
import asyncio as aio
from datetime import datetime
from functools import wraps
from pathlib import Path

# library
import yaml
from dicttoxml import dicttoxml as fxml
from quart import Response, abort, jsonify, request
from quart_openapi import Resource
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid

# module
from avwx_api import counter, handle, structs, token, validators

VALIDATION_ERROR_MESSAGES = {
    401: 'You are missing the "Authorization" header.',
    403: 'Your auth token could not be found, is inactive, or does not have permission to access this resource. Does the value look like "Token 12345abcde"?',
    429: "Your auth token has hit it's daily rate limit. Considder upgrading your plan.",
}


def check_params(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        loc = {self.loc_param: kwargs.get(self.loc_param)}
        params = self.validate_params(**loc)
        if isinstance(params, dict):
            return self.make_response(params, code=400)
        return await func(self, params)

    return wrapper


def token_flag(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.example:
            err_code = await self.validate_token()
            if err_code:
                data = self.make_example_response(err_code)
                return self.make_response(data, code=err_code)
        return await func(self, *args, **kwargs)

    return wrapper


class Base(Resource):
    """
    Base report endpoint
    """

    validator: validators.Schema
    struct: structs.Params
    report_type: str = None
    note: str = None

    # Name of parameter used for report location
    loc_param: str = "station"

    # Filename of the sample response when token validation fails
    # This also tells the token_flag decorator to check for a token
    example: str = None

    # Replace the key's name in the final response
    _key_repl: dict = None
    # Remove the following keys from the final response
    _key_remv: [str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = {}
        self._key_remv = []

    async def validate_token(self) -> int:
        """
        Validates thats an authorization token exists and is active

        Returns None if valid or the error code if not valid
        """
        if not token.PSQL_URI:
            return
        auth_token = request.headers.get("Authorization")
        if not auth_token or len(auth_token) < 10:
            return 401
        # Remove prefix from token value
        auth_token = auth_token.strip().split()[-1]
        token_data = await token.get_token(auth_token)
        if token_data is None or not token.is_paid(token_data):
            return 403
        # Returns True if exceeded rate limit
        limit = token.LIMITS.get(token_data["name"], None)
        if await token.increment_token(auth_token, limit):
            return 429
        return

    def validate_params(self, **kwargs) -> structs.Params:
        """
        Returns all validated request parameters or an error response dict
        """
        try:
            params = {
                "report_type": self.report_type,
                **request.headers,
                **request.args,
                **kwargs,
            }
            # Unpack param lists. Ex: options: ['info,speech'] -> options: 'info,speech'
            for k, v in params.items():
                if isinstance(v, list):
                    params[k] = v[0]
            return self.struct(**self.validator(params))
        except (Invalid, MultipleInvalid) as exc:
            key = exc.path[0]
            return {
                "error": str(exc.msg),
                "param": key,
                "help": validators.HELP.get(key),
            }

    def make_example_response(self, error_code: int) -> dict:
        """
        Returns an example payload when validation fails
        """
        path = Path(__file__).parent.joinpath("examples", f"{self.example}.json")
        data = json.load(path.open())
        msg = VALIDATION_ERROR_MESSAGES[error_code]
        msg += " Here's an example response for testing purposes"
        if isinstance(data, dict):
            data["meta"] = {"validation_error": msg}
        elif isinstance(data, list):
            data.insert(0, {"validation_error": msg})
        return data

    def format_dict(self, output: dict) -> dict:
        """
        Formats a dict by recursively replacing and removing key

        Returns the item as-is if not a dict
        """
        if not isinstance(output, dict):
            return output
        resp = {}
        for k, v in output.items():
            if k in self._key_remv:
                continue
            elif k in self._key_repl:
                k = self._key_repl[k]
            if isinstance(v, dict):
                v = self.format_dict(v)
            elif isinstance(v, list):
                v = [self.format_dict(item) for item in v]
            resp[k] = v
        return resp

    def make_response(
        self, output: dict, format: str = "json", code: int = 200, meta: str = "meta"
    ) -> Response:
        """
        Returns the output string based on format param
        """
        output = self.format_dict(output)
        if "error" in output and meta not in output:
            output["timestamp"] = datetime.utcnow()
        if self.note:
            if meta not in output:
                output[meta] = {}
            output[meta]["note"] = self.note
        if format == "xml":
            root = self.report_type.upper() if self.report_type else "AVWX"
            resp = Response(fxml(output, custom_root=root), mimetype="text/xml")
        elif format == "yaml":
            resp = Response(
                yaml.dump(output, default_flow_style=False), mimetype="text/x-yaml"
            )
        else:
            resp = jsonify(output)
        resp.status_code = code
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp


class Report(Base):
    """
    Fetch Report Endpoint
    """

    validator = validators.report_station
    struct = structs.ReportStationParams

    @crossdomain(origin="*")
    @check_params
    @token_flag
    async def get(self, params: structs.Params) -> Response:
        """
        GET handler returning reports
        """
        nofail = params.onfail == "cache"
        handler = getattr(handle, self.report_type).handle_report
        coros = [
            handler(getattr(params, self.loc_param), params.options, nofail),
            counter.from_params(params, self.report_type),
        ]
        for resp in await aio.gather(*coros):
            # This assumes that secondary coros do not return anything
            if resp is not None:
                data, code = resp
                break
        return self.make_response(data, params.format, code)


class Parse(Base):
    """
    Given report endpoint
    """

    validator = validators.report_given
    struct = structs.ReportGivenParams

    @crossdomain(origin="*")
    @token_flag
    async def post(self) -> Response:
        """
        POST handler to parse given reports
        """
        data = await request.data
        params = self.validate_params(report=data.decode() or None)
        if isinstance(params, dict):
            data, code = params, 400
        else:
            handler = getattr(handle, self.report_type).parse_given
            data, code = handler(params.report, params.options)
            if "station" in data:
                await counter.increment_station(
                    data["station"], self.report_type + "-given"
                )
        return self.make_response(data, params.format, code)


class MultiReport(Base):
    """
    Multiple METAR and TAF reports in one endpoint
    """

    validator = validators.report_stations
    struct = structs.ReportStationsParams
    loc_param = "stations"

    @crossdomain(origin="*")
    @check_params
    @token_flag
    async def get(self, params: structs.Params) -> Response:
        """
        GET handler returning multiple reports
        """
        locs = getattr(params, self.loc_param)
        nofail = params.onfail == "cache"
        handler = getattr(handle, self.report_type).handle_report
        results = await aio.gather(
            *[handler(loc, params.options, nofail) for loc in locs],
            *[
                counter.increment_station(loc.icao, self.report_type + "-multi")
                for loc in locs
            ],
        )
        keys = [loc.icao if hasattr(loc, "icao") else loc for loc in locs]
        data = dict(zip(keys, [r[0] for r in results if r]))
        return self.make_response(data, params.format)


from avwx_api.api import metar, pirep, station, taf
