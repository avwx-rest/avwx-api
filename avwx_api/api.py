"""
Michael duPont - michael@mdupont.com
avwx_api.views - Routes and views for the flask application
"""

# library
import yaml
from dicttoxml import dicttoxml as fxml
from flask import Response, jsonify, request
from flask_restful import Api, Resource
# module
import avwx_api.validators as args
from avwx_api import app
from avwx_api.handling import handle_report, parse_given

api = Api(app)

def is_num(num: str):
    """Checks whether a given string is a valid number"""
    try:
        float(num)
        return True
    except:
        return False

class Endpoint(Resource):
    """Base AVWX report endpoint"""

    parser = None

    @staticmethod
    def check_report_type(rtype: str) -> str:
        """Validate report type"""
        if rtype.lower() not in ('metar', 'taf'):
            return 'Not a valid report type: {}'.format(rtype)

    @staticmethod
    def check_station(station: [str]) -> str:
        """Validate station ID or coord pair"""
        if station is None:
            return
        if not station or len(station) > 2:
            return 'Not a valid station input: {}'.format(station)
        if len(station) == 2 and len([s for s in station if is_num(s)]) != 2:
            return 'Not a valid coordinate pair: {}'.format(station)

    @staticmethod
    def check_options(opts: str) -> str:
        """Validate given request options"""
        if opts:
            bad_opts = [s for s in opts.split(',') if s not in ('info', 'speech', 'summary', 'translate')]
            if bad_opts:
                return 'One or more invalid options were given: {}'.format(bad_opts)

    def get_param(self, key: str, split: bool = False) -> object:
        """Returns the value of a unique key in the header/args"""
        arg = self.parser.parse_args()[key]
        if split:
            return [] if not arg else arg.split(',')
        return arg

    def check_for_errors(self, rtype: str, station: str = None) -> [str]:
        """Returns a list or explanation strings if an error is found, else None"""
        params = self.parser.parse_args()
        station = params['station'] if 'station' in params else station
        errors = [
            self.check_report_type(rtype),
            self.check_station(station),
            self.check_options(params['options'])
        ]
        return [e for e in errors if e]

    def format_response(self, output: dict, rtype: str) -> Response:
        """Returns the output string based on format param"""
        frmt = self.get_param('format')
        if frmt == 'xml':
            return Response(fxml(output, custom_root=rtype.upper()), mimetype='text/xml')
        elif frmt == 'yaml':
            return Response(yaml.dump(output, default_flow_style=False), mimetype='text/x-yaml')
        return jsonify(output)

    def get_report(self, rtype: str, station: str) -> Response:
        """Common request logic for METAR and TAF requests"""
        rtype = rtype.lower()
        station = station.split(',')
        options = self.get_param('options', split=True)
        error = self.check_for_errors(rtype, station=station)
        if error:
            return jsonify({'Error': error})
        nofail = self.get_param('onfail') == 'cache'

        resp = handle_report(rtype, station, options, nofail)

        response = self.format_response(resp, rtype)
        
        # if any, use the http code from the response
        response.status_code = resp.get("Code", 200)
        return response

class ReportEndpoint(Endpoint):
    """Standard report endpoint"""

    parser = args.report

    def get(self, rtype: str, station: str):
        """GET handler"""
        return self.get_report(rtype, station)

class PHPReportEndpoint(Endpoint):
    """Backwards-compatible PHP report endpoint"""

    parser = args.php_report

    def get(self, rtype: str):
        """GET handler"""
        return self.get_report(rtype, self.get_param('station'))

class ParseEndpoint(Endpoint):
    """Given report endpoint"""

    parser = args.given

    def get(self, rtype: str):
        """GET handler"""
        rtype = rtype.lower()
        report = self.get_param('report')
        options = self.get_param('options', split=True) or []
        error = self.check_for_errors(rtype)
        if error:
            return jsonify({'Error': error})
        resp = parse_given(rtype, report, options)
        return self.format_response(resp, rtype)

api.add_resource(ReportEndpoint, '/api/<string:rtype>/<string:station>')
api.add_resource(PHPReportEndpoint, '/api/<string:rtype>.php')
api.add_resource(ParseEndpoint, '/api/parse/<string:rtype>')
