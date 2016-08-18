#!/usr/bin/python3

"""
Routes and views for the flask application.
"""

# pylint: disable=W0702

#stdlib
from datetime import datetime
#library
from flask import Flask, render_template, request, Response, jsonify
#module
from .avwxhandling import handle_report
from .dicttoxml import dicttoxml as fxml

APP = Flask(__name__)

@APP.route('/')
@APP.route('/home')
def home():
    """Renders the home page
    """
    return render_template(
        'index.html',
        title='Home Page',
        year=datetime.now().year,
    )

@APP.route('/api')
def no_report():
    """Returns no report msg
    """
    return jsonify({'Error': 'No report type given'})

@APP.route('/api/metar')
@APP.route('/api/taf')
def no_station():
    """Returns no station msg
    """
    return jsonify({'Error': 'No station given'})

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

def check_for_errors(rtype: str, sid: [str], dfrm: str, opts: [str]):
    """Returns an explanation string if an error is found, else None
    """
    if rtype.lower() not in ('metar', 'taf'):
        return 'Not a valid report type: {}'.format(rtype)
    if not sid or len(sid) > 2:
        return 'Not a valid station input: {}'.format(sid)
    if len(sid) == 2 and len([s for s in sid if is_num(s)]) != 2:
        return 'Not a valid coordinate pair: {}'.format(sid)
    if dfrm not in ['json', 'xml']:
        return 'Not a valid data return format: {}'.format(dfrm)
    bad_opts = [s for s in opts if s not in ('info', 'summary', 'translate')]
    if bad_opts:
        return 'One or more invalid options were given: {}'.format(bad_opts)

def format_response(resp, frmt):
    if frmt == 'xml':
        return Response(fxml(resp, custom_root='METAR'), mimetype='text/xml')
    else:
        return jsonify(resp)

@APP.route('/api/<string:rtype>/<string:station>')
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

@APP.route('/api/<string:rtype>.php')
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
