"""
Michael duPont - michael@mdupont.com
avwx_api.handling - Data handling between inputs, cache, and avwx
"""

# pylint: disable=E1101,W0703

# stdlib
from os import environ
# library
import avwx
from requests import get
# module
from avwx_api.cache import Cache

GN_USER = environ['GN_USER']

CACHE = Cache()

COORD_URL = 'http://api.geonames.org/findNearByWeatherJSON?lat={}&lng={}&username=' + GN_USER

OPTION_KEYS = {
    'summary': 'Summary',
    'speech': 'Speech',
    'translate': 'Translations'
}

ERRORS = [
    'Station Lookup Error: {} not found for {} ({})',
    'Report Parsing Error: Could not parse {} report ({})'
]

def get_data_for_corrds(lat: str, lon: str) -> {str: object}:
    """Return station/report geodata from geonames for a given latitude and longitude.
    Check for 'Error' key in returned dict
    """
    try:
        data = get(COORD_URL.format(lat, lon)).json()
        if 'weatherObservation' in data:
            return data['weatherObservation']
        elif 'status' in data:
            return {'Error':'Coord Lookup Error: ' + str(data['status']['message'])}
        else:
            return {'Error':'Coord Lookup Error: Unknown Error (1)'}
    except Exception as exc:
        return {'Error':'Coord Lookup Error: Unknown Error (0) / ' + str(exc)}

def new_report(rtype: str, station: str, report: str) -> {str: object}:
    """Fetch and parse METAR data for a given station
    
    We can skip fetching the report if geonames already returned it
    """
    parser = (avwx.Metar if rtype == 'metar' else avwx.Taf)(station)
    # Fetch report if one wasn't received via geonames
    if not report:
        try:
            parser.update()
        except avwx.exceptions.InvalidRequest as exc:
            return {'Error': ERRORS[0].format(rtype.upper(), station, exc)}
        except Exception as exc:
            return {'Error': ERRORS[0].format(rtype.upper(), station, exc)}
    else:
        parser.update(report)
    # Retrieve report data
    data = {
        'data': parser.data,
        'translate': parser.translations,
        'summary': parser.summary
    }
    if rtype == 'metar':
        data['speech'] = parser.speech
    # Update the cache with the new report data
    CACHE.update(rtype, data)
    return data

def format_report(rtype: str, data: {str: object}, options: [str]) -> {str: object}:
    """Formats the report/cache data into the expected response format
    """
    ret = data['data']
    if rtype == 'metar':
        for opt, key in OPTION_KEYS.items():
            if opt in options:
                ret[key] = data[opt]
    else:
        if 'translate' in options:
            ret['Translations'] = data['translate']
        if 'summary' in options:
            for i in range(len(ret['Forecast'])):
                ret['Forecast'][i]['Summary'] = data['summary'][i]
    return ret

def handle_report(rtype: str, loc: [str], opts: [str]) -> {str: object}:
    """Returns weather data for the given report type, station, and options

    Uses a cache to store recent report hashes which are (at most) two minutes old
    """
    if len(loc) == 2:
        #Do things given goedata contains station and metar report
        geodata = get_data_for_corrds(loc[0], loc[1])
        if 'Error' in geodata:
            return geodata
        station = geodata['ICAO']
        report = geodata['observation'] if rtype == 'metar' else None
    else:
        #Do things given only station
        station = loc[0].upper()
        report = None
    # Fetch an existing and up-to-date cache or make a new report
    data = CACHE.get(rtype, station) or new_report(rtype, station, report)
    if 'Error' in data:
        return data
    # Format the return data
    data = format_report(rtype, data, opts)
    #Add station info if requested
    if 'info' in opts:
        data['Info'] = avwx.Report(station).station_info
    return data

def parse_given(rtype: str, report: str, opts: [str]):
    """Attepts to parse a given report supplied by the user
    """
    if len(report) < 4:
        return {'Error': 'Could not find station at beginning of report'}
    station = report[:4]
    try:
        ureport = avwx.Metar(station) if rtype == 'metar' else avwx.Taf(station)
        ureport.update(report)
        rdict = ureport.data
        if 'translate' in opts or 'summary' in opts:
            rdict['Translations'] = ureport.translations
            if rtype == 'metar':
                if 'summary' in opts:
                    rdict['Summary'] = ureport.summary
                if 'speech' in opts:
                    rdict['Speech'] = ureport.speech
            else:
                if 'summary' in opts:
                    #Special handling for TAF summary response
                    for i, forecast in enumerate(ureport.translations['Forecast']):
                        rdict['Forecast'][i]['Summary'] = avwx.summary.taf(forecast)
        #Add station info if requested
        if 'info' in opts:
            rdict['Info'] = ureport.station_info
        return rdict
    except avwx.exceptions.BadStation as exc:
        return {'Error': ERRORS[0].format(rtype, exc)}
    except Exception as exc:
        return {'Error': ERRORS[1].format(rtype, exc)}
