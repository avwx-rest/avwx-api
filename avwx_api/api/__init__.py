"""
Michael duPont - michael@mdupont.com
avwx_api.api - Functional API endpoints separate from static views
"""

# stdlib
import json
import asyncio as aio
from functools import wraps
from os import path
# library
import yaml
from dicttoxml import dicttoxml as fxml
from quart import Response, abort, jsonify, request
from quart_openapi import Resource
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid
# module
from avwx_api import handle, structs, token, validators

VALIDATION_ERROR_MESSAGES = {
    401: 'You are missing the "Authorization" header.',
    403: 'Your auth token could not be found or is inactive. Does the value look like "Token 12345abcde"?',
}

_DIR = path.dirname(path.realpath(__file__))

def check_params_with_station(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        station = kwargs.get('station') or kwargs.get('stations')
        params = self.validate_params(station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
            resp.headers['X-Robots-Tag'] = 'noindex'
            return resp
        return await func(self, params, *args, **kwargs)
    return wrapper

def token_flag(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.example:
            err_code = await self.validate_token()
            if err_code:
                resp = jsonify(self.make_example_response(err_code))
                resp.status_code = err_code
                resp.headers['X-Robots-Tag'] = 'noindex'
                return resp
        return await func(self, *args, **kwargs)
    return wrapper


class Base(Resource):
    """
    Base report endpoint
    """

    validator = validators.report
    struct = structs.FetchParams
    report_type: str = None
    note: str = None

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
        auth_token = request.headers.get('Authorization')
        if not auth_token or len(auth_token) < 10:
            return 401
        # Remove 'Token ' from token value
        if not await token.validate_token(auth_token.strip()[7:]):
            return 403

    def validate_params(self, **kwargs) -> structs.Params:
        """
        Returns all validated request parameters or an error response dict
        """
        try:
            params = {'report_type': self.report_type, **request.headers, **request.args, **kwargs}
            # Unpack param lists. Ex: options: ['info,speech'] -> options: 'info,speech'
            for k, v in params.items():
                if isinstance(v, list):
                    params[k] = v[0]
            return self.struct(**self.validator(params))
        except (Invalid, MultipleInvalid) as exc:
            key = exc.path[0]
            return {
                'error': str(exc.msg),
                'param': key,
                'help': validators.HELP.get(key)
            }

    def make_example_response(self, error_code: int) -> dict:
        """
        Returns an example payload when validation fails
        """
        data = json.load(open(path.join(_DIR, 'examples', self.example+'.json')))
        msg = VALIDATION_ERROR_MESSAGES[error_code]
        msg += " Here's an example response for testing purposes"
        data['meta'] = {'validation_error': msg}
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

    def format_response(self, output: dict, format: str, meta: str = 'meta') -> Response:
        """
        Returns the output string based on format param
        """
        output = self.format_dict(output)
        if self.note:
            if meta not in output:
                output[meta] = {}
            output[meta]['note'] = self.note
        if format == 'xml':
            return Response(fxml(output, custom_root=self.report_type.upper()), mimetype='text/xml')
        elif format == 'yaml':
            return Response(yaml.dump(output, default_flow_style=False), mimetype='text/x-yaml')
        return jsonify(output)

class Report(Base):
    """
    """

    @crossdomain(origin='*')
    @check_params_with_station
    @token_flag
    async def get(self, params: structs.Params, station: str) -> Response:
        """
        GET handler returning reports
        """
        nofail = params.onfail == 'cache'
        handler = getattr(handle, self.report_type).handle_report
        data, code = await handler(params.station, params.options, nofail)
        resp = self.format_response(data, params.format)
        resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

class LegacyReport(Report):
    """
    Legacy report endpoint to return data in pre-Sept2018 format

    Will eventually be phased out
    """

    key_repl = {
        'clouds': 'Cloud-List',
        'dewpoint_decimal': 'Dew-Decimal',
        'icing': 'Icing-List',
        'other': 'Other-List',
        'raw': 'Raw-Report',
        'runway_visibility': 'Runway-Vis-List',
        'temperature_decimal': 'Temp-Decimal',
        'turbulance': 'Turb-List',
        'wind_variable_direction': 'Wind-Variable-Dir',
    }

    note = ("The /api/<report-type> endpoint will switch to the "
            "/api/preview/<report-type> format on April 1, 2019. "
            "If you need more time, use /api/legacy/<report-type>")

    def revert_value(self, value: object) -> object:
        """
        Reverts a value based on content type
        """
        if isinstance(value, dict):
            # Revert cloud layer
            if 'modifier' in value:
                temp = [value['type'], str(value['base']).zfill(3)]
                if value['modifier'] is not None:
                    temp.append(value['modifier'])
                return temp
            # Revert number or timestamp
            elif 'repr' in value:
                return value['repr']
            # Else recursive call on embedded dict
            else:
                return self.format_dict(value)
        elif isinstance(value, list):
            return [self.revert_value(item) for item in value]
        elif value is None:
            return ''
        return value

    def format_dict(self, data: dict) -> dict:
        """
        Reverts a dict's keys and values to the legacy format
        """
        resp = {}
        for k, v in data.items():
            # Special case for TAF line
            if k == 'raw' and 'wind_shear' in data:
                k = 'Raw-Line'
            elif k in self.key_repl:
                k = self.key_repl[k]
            # 'flight_rules' -> 'Flight-Rules'
            else:
                k = k.replace('_', '-').title()
            resp[k] = self.revert_value(v)
        return resp

    @crossdomain(origin='*')
    @check_params_with_station
    async def get(self, params: structs.Params, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports in the legacy format
        """
        nofail = params.onfail == 'cache'
        handler = getattr(handle, self.report_type).handle_report
        data, code = await handler(params.station, params.options, nofail)
        resp = self.format_response(data, params.format, meta='Meta')
        resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

class Parse(Base):
    """
    Given report endpoint
    """

    validator = validators.given
    struct = structs.GivenParams

    @crossdomain(origin='*')
    @token_flag
    async def post(self) -> Response:
        """
        POST handler to parse given METAR and TAF reports
        """
        data = await request.data
        params = self.validate_params(report=data.decode() or None)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
            resp.headers['X-Robots-Tag'] = 'noindex'
            return resp
        # Handle token validation
        code = None
        if self.example:
            code = await self.validate_token()
        if code:
            data = self.make_example_response(err)
        else:
            handler = getattr(handle, self.report_type).parse_given
            data, code = handler(params.report, params.options)
            resp = self.format_response(data, params.format)
        resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

class MultiReport(Base):
    """
    Multiple METAR and TAF reports in one endpoint
    """

    validator = validators.multi_report

    @crossdomain(origin='*')
    @check_params_with_station
    @token_flag
    async def get(self, params: structs.Params, stations: str) -> Response:
        """
        GET handler returning multiple METAR and TAF reports
        """
        nofail = params.onfail == 'cache'
        handler = getattr(handle, self.report_type).handle_report
        results = await aio.gather(*[handler(
            [station],
            params.options,
            nofail
        ) for station in params.station])
        data = dict(zip(params.station, [r[0] for r in results]))
        resp = self.format_response(data, params.format)
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

from avwx_api.api import metar, pirep, taf
