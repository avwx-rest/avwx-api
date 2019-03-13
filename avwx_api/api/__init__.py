"""
Michael duPont - michael@mdupont.com
avwx_api.api - Functional API endpoints separate from static views
"""

# stdlib
import asyncio as aio
# library
import yaml
from dicttoxml import dicttoxml as fxml
from quart import Response, abort, jsonify, request
from quart_openapi import Resource
from quart_openapi.cors import crossdomain
from voluptuous import Invalid, MultipleInvalid
# module
from avwx_api import handle, structs, token, validators

async def validate_token() -> (str, int):
    """
    Aborts request if a header token is not valid
    """
    if not token.PSQL_URI:
        return
    auth_token = request.headers.get('Authorization')
    if not auth_token or len(auth_token) < 10:
        abort(401)
    # Remove 'Token ' from token value
    if not await token.validate_token(auth_token.strip()[7:]):
        abort(403)

class Base(Resource):
    """
    Base report endpoint
    """

    validator = validators.report
    struct = structs.FetchParams
    report_type: str = None
    note: str = None

    # Replace the key's name in the final response
    _key_repl: dict = None
    # Remove the following keys from the final response
    _key_remv: [str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_repl = {}
        self._key_remv = []

    def validate(self, **kwargs) -> structs.Params:
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
    async def get(self, station: str) -> Response:
        """
        GET handler returning reports
        """
        params = self.validate(station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
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
    async def get(self, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports in the legacy format
        """
        params = self.validate(station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
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
    async def post(self) -> Response:
        """
        POST handler to parse given METAR and TAF reports
        """
        data = await request.data
        params = self.validate(report=data.decode() or None)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
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
    async def get(self, stations: str) -> Response:
        """
        GET handler returning multiple METAR and TAF reports
        """
        await validate_token()
        params = self.validate(station=stations)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            handler = getattr(handle, self.report_type).handle_report
            results = await aio.gather(*[handler(
                [station],
                params.options,
                nofail
            ) for station in params.station])
            results = dict(zip(params.station, [r[0] for r in results]))
            resp = self.format_response(results, params.format)
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

from avwx_api.api import metar, pirep, taf
