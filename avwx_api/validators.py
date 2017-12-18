"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter and header validators
"""

# stdlib
from copy import copy
# library
from flask_restful.reqparse import RequestParser

PARAMS = {
    'format': {
        'default': 'json',
        'choices': ('json', 'xml', 'yaml'),
        'help': 'Accepted response formats (json, xml, yaml)'
    },
    'onfail': {
        'default': 'error',
        'help': 'Desired behavior when report fetch fails (error, cache)'
    },
    'options': {
        'default': '',
        'help': 'Response content and parsing options. Ex: "info,summary"'
    },
    'report': {
        'required': True,
        'help': 'Raw report string to be parsed. Must be param encoded or in headers'
    },
    'station': {
        'required': True,
        'help': 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"'
    }
}

def make_parser(args: [str]) -> RequestParser:
    """Create a RequestParser with the given arguements"""
    parser = RequestParser(bundle_errors=True)
    for arg in args:
        parser.add_argument(arg, location=['args', 'headers'], **PARAMS[arg])
    return parser

report = make_parser(['format', 'onfail', 'options'])
php_report = make_parser(['format', 'onfail', 'options', 'station'])
given = make_parser(['format', 'options', 'report'])
