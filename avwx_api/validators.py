"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter validators
"""

# stdlib
from typing import Callable
# library
from avwx.core import valid_station
from avwx.exceptions import BadStation
from voluptuous import All, In, Invalid, Required, Schema, REMOVE_EXTRA

HELP = {
    'format': 'Accepted response formats (json, xml, yaml)',
    'onfail': 'Desired behavior when report fetch fails (error, cache)',
    'options': 'Response content and parsing options. Ex: "info,summary"',
    'report': 'Raw report string to be parsed. Given in the POST body as plain text',
    'report_type': 'Weather report type (metar, taf)',
    'station': 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"'
}

def Location(loc: str) -> [str]:
    """
    Validates a station ident or coordinate pair string
    """
    loc = loc.upper().split(',')
    if len(loc) == 1:
        try:
            valid_station(loc[0])
        except BadStation:
            raise Invalid(f'{loc[0]} is not a valid ICAO station ident')
    elif len(loc) == 2:
        try:
            float(loc[0])
            float(loc[1])
        except:
            raise Invalid(f'{loc} is not a valid coordinate pair')
    else:
        raise Invalid(f'{loc} is not a valid station/coordinate pair')
    return loc

def MultiStation(stations: str) -> [str]:
    """
    Validates a comma-separated list of station idents
    """
    stations = stations.upper().split(',')
    if not stations:
        raise Invalid('Could not find any stations in the request')
    if len(stations) > 10:
        raise Invalid('Multi requests are limited to 10 stations or less')
    for station in stations:
        try:
            valid_station(station)
        except BadStation:
            raise Invalid(f'{station} is not a valid ICAO station ident')
    return stations

def SplitIn(values: (str,)) -> Callable:
    """
    Returns a validator to check for given values in a comma-separated string
    """
    def validator(csv: str) -> str:
        if not csv:
            return []
        split = csv.split(',')
        for val in split:
            if val not in values:
                raise Invalid(f"'{val}' could not be found in {values}")
        return split
    return validator

_shared = {
    Required('format', default='json'): All(str, In(('json', 'xml', 'yaml'))),
    Required('options', default=''): All(str, SplitIn(('info', 'translate', 'summary', 'speech'))),
    Required('report_type'): All(str, In(('metar', 'taf')))
}

_report = {
    **_shared,
    Required('onfail', default='error'): All(str, In(('error', 'cache'))),
    Required('station'): All(str, Location),
}

report = Schema(_report, extra=REMOVE_EXTRA)

given = Schema({
    **_shared,
    'report': str,
}, extra=REMOVE_EXTRA)

multi_report = Schema({
    **_report,
    Required('station'): All(str, MultiStation),
}, extra=REMOVE_EXTRA)
