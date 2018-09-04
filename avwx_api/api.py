"""
Michael duPont - michael@mdupont.com
avwx_api.api - Functional API endpoints separate from static views
"""

# library
import yaml
from dicttoxml import dicttoxml as fxml
from flask import Response, jsonify, request
from flask_restful import Api, Resource
from voluptuous import Invalid, MultipleInvalid
# module
from avwx_api import app, structs, validators
from avwx_api.handling import handle_report, parse_given

api = Api(app)

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

    def get(self, rtype: str, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports
        """
        params = self.validate(rtype.lower(), station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            data, code = handle_report(rtype, params.station, params.options, nofail)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

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

    def get(self, rtype: str, station: str) -> Response:
        """
        GET handler returning METAR and TAF reports in the legacy format
        """
        params = self.validate(rtype.lower(), station=station)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            nofail = params.onfail == 'cache'
            data, code = handle_report(rtype, params.station, params.options, nofail)
            data = self.revert_dict(data)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

class LegacyCopy(LegacyReportEndpoint):
    pass

class ParseEndpoint(ReportEndpoint):
    """
    Given report endpoint
    """

    validator = validators.given
    struct = structs.GivenParams

    def post(self, rtype: str) -> Response:
        """
        POST handler to parse given METAR and TAF reports
        """
        params = self.validate(rtype.lower(), report=request.data.decode() or None)
        if isinstance(params, dict):
            resp = jsonify(params)
            resp.status_code = 400
        else:
            data, code = parse_given(rtype, params.report, params.options)
            resp = self.format_response(data, params.format, rtype)
            resp.status_code = code
        resp.headers['X-Robots-Tag'] = 'noindex'
        return resp

api.add_resource(ReportEndpoint, '/api/preview/<string:rtype>/<string:station>')
api.add_resource(LegacyCopy, '/api/<string:rtype>/<string:station>')
api.add_resource(LegacyReportEndpoint, '/api/legacy/<string:rtype>/<string:station>')
api.add_resource(ParseEndpoint, '/api/parse/<string:rtype>')
