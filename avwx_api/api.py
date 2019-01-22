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
from avwx_api import app, structs, token, validators
from avwx_api.handling import handle_report, parse_given

async def validate_token() -> (str, int):
    """
    Aborts request if a header token is not valid
    """
    if not token.PSQL_URI:
        return
    auth_token = request.headers.get('Authorization')
    if not auth_token:
        abort(401)
    # Remove 'Token ' from token value
    if not await token.validate_token(auth_token.strip()[7:]):
        abort(403)

@app.route('/api/preview/<string:rtype>/<string:station>')
class ReportEndpoint(Resource):
    """
    METAR and TAF report endpoint
    """

    validator = validators.report
    struct = structs.FetchParams

    def validate(self, rtype: str, **kwargs) -> structs.Params:
        """
        Returns all validated request parameters or an error response dict
        """
        try:
            params = {'report_type': rtype.lower(), **request.headers, **request.args, **kwargs}
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

    @staticmethod
    def format_response(output: dict, format: str, rtype: str) -> Response:
        """
        Returns the output string based on format param
        """
        if format == 'xml':
            return Response(fxml(output, custom_root=rtype.upper()), mimetype='text/xml')
        elif format == 'yaml':
            return Response(yaml.dump(output, default_flow_style=False), mimetype='text/x-yaml')
        return jsonify(output)

    @crossdomain(origin='*')
    async def get(self, rtype: str, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports
        """
        params = self.validate(rtype.lower(), station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            data, code = await handle_report(rtype, params.station, params.options, nofail)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

@app.route('/api/<string:rtype>/<string:station>')
class LegacyReportEndpoint(ReportEndpoint):
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
                temp = [value['type'], str(value['altitude']).zfill(3)]
                if value['modifier'] is not None:
                    temp.append(value['modifier'])
                return temp
            # Revert number or timestamp
            elif 'repr' in value:
                return value['repr']
            # Else recursive call on embedded dict
            else:
                return self.revert_dict(value)
        elif isinstance(value, list):
            return [self.revert_value(item) for item in value]
        elif value is None:
            return ''
        return value

    def revert_dict(self, data: dict) -> dict:
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
    async def get(self, rtype: str, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports in the legacy format
        """
        params = self.validate(rtype.lower(), station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            data, code = await handle_report(rtype, params.station, params.options, nofail)
            if self.note:
                if 'meta' not in data:
                    data['meta'] = {}
                data['meta']['note'] = self.note
            data = self.revert_dict(data)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

@app.route('/api/legacy/<string:rtype>/<string:station>')
class LegacyCopy(LegacyReportEndpoint):
    
    note = ("The legacy endpoint will be available until July 1, 2019")

@app.route('/api/<string:rtype>/parse')
class ParseEndpoint(LegacyReportEndpoint):
    """
    Given report endpoint
    """

    validator = validators.given
    struct = structs.GivenParams

    @crossdomain(origin='*')
    async def post(self, rtype: str) -> Response:
        """
        POST handler to parse given METAR and TAF reports
        """
        data = await request.data
        params = self.validate(rtype.lower(), report=data.decode() or None)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            data, code = parse_given(rtype, params.report, params.options)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

@app.route('/api/multi/<string:rtype>/<string:stations>')
class MultiReportEndpoint(ReportEndpoint):
    """
    Multiple METAR and TAF reports in one endpoint
    """

    validator = validators.multi_report

    @crossdomain(origin='*')
    async def get(self, rtype: str, stations: str) -> Response:
        """
        GET handler returning multiple METAR and TAF reports
        """
        await validate_token()
        params = self.validate(rtype.lower(), station=stations)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            results = await aio.gather(*[handle_report(
                'metar',
                [station],
                params.options,
                nofail
            ) for station in params.station])
            results = dict(zip(params.station, [r[0] for r in results]))
            resp = self.format_response(results, params.format, rtype)
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp
