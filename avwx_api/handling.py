"""
Michael duPont - michael@mdupont.com
avwx_api.handling - Data handling between inputs, cache, and avwx
"""

# pylint: disable=E1101,W0703

# stdlib
from dataclasses import asdict
from datetime import datetime
from os import environ
# library
import aiohttp
import avwx
import rollbar
# module
from avwx_api import cache

GN_USER = environ.get('GN_USER', '')

COORD_URL = 'http://api.geonames.org/findNearByWeatherJSON?lat={}&lng={}&username=' + GN_USER

OPTION_KEYS = ('summary', 'speech', 'translate')

ERRORS = [
    'Station Lookup Error: {} not found for {}. There might not be a current report in ADDS',
    'Report Parsing Error: Could not parse {} report. Please contact the admin with raw report',
    'Station Lookup Error: {} does not appear to be a valid station. Please contact the admin',
]

_timeout = aiohttp.ClientTimeout(total=10)

async def get_data_for_corrds(lat: str, lon: str) -> (dict, int):
    """
    Return station/report geodata from geonames for a given latitude and longitude.
    
    Check for 'Error' key in returned dict
    """
    try:
        async with aiohttp.ClientSession(timeout=_timeout) as sess:
            async with sess.get(COORD_URL.format(lat, lon)) as resp:
                data = await resp.json()
        if 'weatherObservation' in data:
            return data['weatherObservation'], 200
        elif 'status' in data:
            return {'error':'Coord Lookup Error: ' + str(data['status']['message'])}, 400
        rollbar.report_exc_info()
        return {'error':'Coord Lookup Error: Unknown Error (1)'}, 500
    except Exception as exc:
        print(exc)
        rollbar.report_exc_info()
        return {'error':'Coord Lookup Error: Unknown Error (0)'}, 500

async def new_report(rtype: str, station: str, report: str) -> (dict, int):
    """
    Fetch and parse report data for a given station

    We can skip fetching the report if geonames already returned it
    """
    try:
        parser = (avwx.Metar if rtype == 'metar' else avwx.Taf)(station)
    except avwx.exceptions.BadStation as exc:
        return {'error': str(exc)}, 400
    # Fetch report if one wasn't received via geonames
    if not report:
        try:
            if not await parser.async_update():
                return {'error': ERRORS[0].format(rtype.upper(), station)}, 400
        except avwx.exceptions.InvalidRequest as exc:
            print('Invalid Request:', exc)
            return {'error': ERRORS[0].format(rtype.upper(), station)}, 400
        except Exception as exc:
            print('unknown Error', exc)
            rollbar.report_exc_info()
            return {'error': ERRORS[0].format(rtype.upper(), station)}, 500
    else:
        parser.update(report)
    # Retrieve report data
    data = {
        'data': asdict(parser.data),
        'translate': asdict(parser.translations),
        'summary': parser.summary,
        'speech': parser.speech,
    }
    data['data']['units'] = asdict(parser.units)
    # Update the cache with the new report data
    await cache.update(rtype, data)
    return data, 200

def format_report(rtype: str, data: {str: object}, options: [str]) -> {str: object}:
    """
    Formats the report/cache data into the expected response format
    """
    ret = data['data']
    for opt in OPTION_KEYS:
        if opt in options:
            if opt == 'summary' and rtype == 'taf':
                for i in range(len(ret['forecast'])):
                    ret['forecast'][i]['summary'] = data['summary'][i]
            else:
                ret[opt] = data.get(opt)
    return ret

async def handle_report(rtype: str, loc: [str], opts: [str], nofail: bool = False) -> (dict, int):
    """
    Returns weather data for the given report type, station, and options
    Also returns the appropriate HTTP response code

    Uses a cache to store recent report hashes which are (at most) two minutes old
    If nofail and a new report can't be fetched, the cache will be returned with a warning
    """
    if len(loc) == 2:
        # Do things given goedata contains station and metar report
        geodata, code = await get_data_for_corrds(loc[0], loc[1])
        if code != 200:
            return geodata, code
        station = geodata['ICAO']
        report = geodata['observation'] if rtype == 'metar' else None
    else:
        # Do things given only station
        station = loc[0].upper()
        report = None
    # Fetch an existing and up-to-date cache or make a new report
    data, code = await cache.get(rtype, station), 200
    if data is None:
        data, code = await new_report(rtype, station, report)
    resp = {'meta': {'timestamp': datetime.utcnow()}}
    if 'timestamp' in data:
        resp['meta']['cache-timestamp'] = data['timestamp']
    # Handle errors according to nofail arguement
    if code != 200:
        if nofail:
            cache_data = await cache.get(rtype, station)
            if cache_data is None:
                resp['error'] = 'No report or cache was found for the requested station'
                return resp, 400
            data = cache_data
            resp['meta'].update({
                'cache-timestamp': data['timestamp'],
                'warning': 'A no-fail condition was requested. This data might be out of date',
            })
        else:
            resp.update(data)
            return resp, code
    # Format the return data
    resp.update(format_report(rtype, data, opts))
    # Add station info if requested
    if 'info' in opts:
        try:
            resp['info'] = asdict(avwx.Station.from_icao(station))
        except avwx.exceptions.BadStation:
            resp['info'] = {}
    return resp, code

def parse_given(rtype: str, report: str, opts: [str]) -> (dict, int):
    """
    Attepts to parse a given report supplied by the user
    """
    if len(report) < 4 or '{' in report:
        return {
            'error': 'Could not find station at beginning of report',
            'timestamp': datetime.utcnow()
        }, 400
    station = report[:4]
    try:
        ureport = avwx.Metar(station) if rtype == 'metar' else avwx.Taf(station)
        ureport.update(report)
        resp = asdict(ureport.data)
        resp['meta'] = {'timestamp': datetime.utcnow()}
        if 'translate' in opts:
            resp['translations'] = asdict(ureport.translations)
        if 'summary' in opts:
            if rtype == 'taf':
                for i in range(len(ureport.translations['forecast'])):
                    resp['forecast'][i]['summary'] = ureport.summary[i]
            else:
                resp['summary'] = ureport.summary
        if 'speech' in opts:
            resp['speech'] = ureport.speech
        # Add station info if requested
        if 'info' in opts:
            try:
                resp['info'] = asdict(ureport.station_info)
            except avwx.exceptions.BadStation:
                resp['info'] = {}
        return resp, 200
    except avwx.exceptions.BadStation:
        return {'error': ERRORS[2].format(station), 'timestamp': datetime.utcnow()}, 400
    except:
        rollbar.report_exc_info()
        return {'error': ERRORS[1].format(rtype), 'timestamp': datetime.utcnow()}, 500