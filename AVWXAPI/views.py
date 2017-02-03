#!/usr/bin/python3

"""
Routes and views for the flask application.
"""

# pylint: disable=W0702

#library
import yaml
from flask import request, Response, jsonify
#module
from AVWXAPI import app
from .avwxhandling import handle_report, parse_given
from .dicttoxml import dicttoxml as fxml

##-------------------------------------------------------##
# Static Web Pages
@app.route('/')
@app.route('/home')
def home():
    """Returns static home page"""
    return app.send_static_file('html/home.html')
@app.route('/about')
def about():
    """Returns static about page"""
    return app.send_static_file('html/about.html')
@app.route('/contact')
def contact():
    """Returns static contact page"""
    return app.send_static_file('html/contact.html')
@app.route('/documentation')
def documentation():
    """Returns static documentation page"""
    return app.send_static_file('html/documentation.html')
@app.route('/updates')
def updates():
    """Returns static updates page"""
    return app.send_static_file('html/updates.html')

##-------------------------------------------------------##
# API Routing Errors
@app.route('/api')
def no_report():
    """Returns no report msg
    """
    return jsonify({'Error': 'No report type given'})

@app.route('/api/metar')
@app.route('/api/taf')
def no_station():
    """Returns no station msg
    """
    return jsonify({'Error': 'No station given'})

##-------------------------------------------------------##
# API Helper Functions
def get_req_value(key, split: bool=True):
    """Returns the value of a unique key in the header/args
    """
    ret = request.headers.get(key)
    if not ret:
        ret = request.args.get(key)
    return ret.split(',') if ret and split else ret

def get_settings(default_format: str='json'):
    """Returns the shared request settings
    """
    val = get_req_value('options')
    if not val:
        val = []
    data_format = get_req_value('format')
    if not data_format:
        data_format = [default_format]
    return val, data_format[0].lower()

def is_num(num: str):
    """Checks whether a given string is a valid number
    """
    try:
        float(num)
        return True
    except:
        return False

def check_for_errors(rtype: str, sid: [str], dfrm: str, opts: [str], ignore_station: bool=False):
    """Returns an explanation string if an error is found, else None
    """
    if rtype.lower() not in ('metar', 'taf'):
        return 'Not a valid report type: {}'.format(rtype)
    if not ignore_station:
        if not sid or len(sid) > 2:
            return 'Not a valid station input: {}'.format(sid)
        if len(sid) == 2 and len([s for s in sid if is_num(s)]) != 2:
            return 'Not a valid coordinate pair: {}'.format(sid)
    if dfrm not in ['json', 'xml', 'yaml']:
        return 'Not a valid data return format: {}'.format(dfrm)
    bad_opts = [s for s in opts if s not in ('info', 'speech', 'summary', 'translate')]
    if bad_opts:
        return 'One or more invalid options were given: {}'.format(bad_opts)

def format_response(resp, frmt):
    """Returns a given response into the desired format

    Accepts 'xml' or defaults to JSON
    """
    if frmt == 'xml':
        return Response(fxml(resp, custom_root='METAR'), mimetype='text/xml')
    elif frmt == 'yaml':
        return yaml.dump(resp, default_flow_style=False)
    else:
        return jsonify(resp)

##-------------------------------------------------------##
# API Routing Endpoints
@app.route('/api/<string:rtype>/<string:station>')
def new_style_report(rtype: str, station: str):
    """Returns the report for a given type and station
    """
    station = station.split(',')
    options, data_format = get_settings()
    error = check_for_errors(rtype, station, data_format, options)
    if error:
        return jsonify({'Error': error})
    resp = handle_report(rtype, station, options)
    return format_response(resp, data_format)

@app.route('/api/<string:rtype>.php')
def old_style_report(rtype: str):
    """Handles the previous endpoint and data input
    """
    #Get the station or coordinates
    station = get_req_value('station')
    if not station:
        station = [get_req_value('lat'), get_req_value('lon')]
    #If we have neither, return the special error
    if station == [None, None]:
        return jsonify({'Error': 'No station or coordinates given'})
    options, data_format = get_settings(default_format='xml')
    error = check_for_errors(rtype, station, data_format, options)
    if error:
        return jsonify({'Error': error})
    resp = handle_report(rtype, station, options)
    return format_response(resp, data_format[0])

@app.route('/api/parse/<string:rtype>')
def given_report(rtype: str):
    """Returns the attmpted parse of a user-supplied report
    """
    report = get_req_value('report')
    if not report:
        return jsonify({'Error': 'No report string given'})
    report = report[0]
    options, data_format = get_settings()
    error = check_for_errors(rtype, None, data_format, options, ignore_station=True)
    if error:
        return jsonify({'Error': error})
    resp = parse_given(rtype, report, options)
    return format_response(resp, data_format)

##-------------------------------------------------------##
# AI Service Endpoints

RTYPE_MAP = {
    'fetch_metar': 'metar'#,
    #'fetch_taf': 'taf'
}

@app.route('/api/apiai', methods=['POST'])
def api_ai_report():
    """Endpoint servicing api.ai service for Slack, FBM, Google Assistant/Home
    """
    req_body = request.get_json()
    action = req_body['result']['action']
    if action not in RTYPE_MAP:
        return {
            'speech': 'This action is not yet supported',
            'displayText': 'This action is not yet supported',
            'data': {},
            'contextOut': [],
            'source': 'avwx.rest'
        }
    rtype = RTYPE_MAP[action]
    station = req_body['result']['parameters']['airport']['ICAO']
    wxret = handle_report(rtype, [station], ['speech'])
    resp = {
        'speech': wxret['Speech'],
        'displayText': wxret['Summary'],
        'data': wxret,
        'contextOut': [],
        'source': 'avwx.rest'
    }
    return jsonify(resp)
