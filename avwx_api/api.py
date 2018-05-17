"""
Michael duPont - michael@mdupont.com
avwx_api.views - Routes and views for the flask application
"""

# library
import yaml
from dicttoxml import dicttoxml as fxml
from flask import Response, jsonify, request
from flask_restful import Api, Resource
from voluptuous import Invalid, MultipleInvalid
# module
import avwx_api.validators as validators
from avwx_api import app
from avwx_api.handling import handle_report, parse_given

api = Api(app)

KEYS = ('format', 'onfail', 'options', 'report', 'report_type', 'station')

class ReportEndpoint(Resource):
    """Report endpoint"""

    validator = validators.report

    def validate(self, rtype: str, station: str = None) -> dict:
        """Returns all validated request parameters or an error response dict"""
        try:
            params = {'report_type': rtype}
            for group in (request.headers, request.args):
                for k, v in group.items():
                    if k in KEYS:
                        params[k] = v
            if station is not None:
                params['station'] = station
            return self.validator(params)
        except (Invalid, MultipleInvalid) as exc:
            key = exc.path[0]
            return {
                'Error': str(exc.msg),
                'Param': key,
                'Help': validators.HELP.get(key)
            }

    @staticmethod
    def format_response(output: dict, format: str, rtype: str) -> Response:
        """Returns the output string based on format param"""
        if format == 'xml':
            return Response(fxml(output, custom_root=rtype.upper()), mimetype='text/xml')
        elif format == 'yaml':
            return Response(yaml.dump(output, default_flow_style=False), mimetype='text/x-yaml')
        return jsonify(output)

    def get(self, rtype: str, station: str) -> Response:
        """GET handler"""
        params = self.validate(rtype.lower(), station)
        if 'Error' in params:
            resp = jsonify(params)
            resp.status_code = 400
        else:
            opts = params.get('options', '')
            nofail = params['onfail'] == 'cache'
            data, code = handle_report(rtype, params['station'], opts, nofail)
            resp = self.format_response(data, params['format'], rtype)
            resp.status_code = code
        return resp

class LegacyReportEndpoint(ReportEndpoint):
    """Legacy report endpoint to duplicate functionality for now"""
    pass

class ParseEndpoint(ReportEndpoint):
    """Given report endpoint"""

    validator = validators.given

    def get(self, rtype: str) -> Response:
        """GET handler"""
        params = self.validate(rtype.lower())
        if 'Error' in params:
            resp = jsonify(params)
            resp.status_code = 400
        else:
            opts = params.get('options', '')
            data, code = parse_given(rtype, params['report'], opts)
            resp = self.format_response(data, params['format'], rtype)
            resp.status_code = code
        return resp

api.add_resource(ReportEndpoint, '/api/<string:rtype>/<string:station>')
api.add_resource(LegacyReportEndpoint, '/api/legacy/<string:rtype>/<string:station>')
api.add_resource(ParseEndpoint, '/api/parse/<string:rtype>')
