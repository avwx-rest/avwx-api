#!/usr/bin/python3

"""
Data handling between inputs, redis, and avwx function library

Requires credentials.py
REDIS_CRED = {
    'host': 'redis_host_url',
    'password': 'redis_pw',
    'port': 6380
}
GN_USER = 'geonames_username'
"""

# pylint: disable=E1101,W0703

#stdlib
from copy import deepcopy
from datetime import datetime, timedelta
from ast import literal_eval
#library
import avwx
import redis
from requests import get
#module
from avwx_api.credentials import GN_USER, REDIS_CRED

COORD_URL = 'http://api.geonames.org/findNearByWeatherJSON?lat={}&lng={}&username=' + GN_USER
HASH_KEYS = ('timestamp', 'standard', 'translate', 'summary', 'speech')

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

def data_level(opts: [str]):
    """Returns data level key depending on values in options (descending order)
    """
    for key in HASH_KEYS[:1:-1]:
        if key in opts:
            return key
    return HASH_KEYS[1]

def get_metar_hash(station: str, report: str) -> {str: object}:
    """Get the full METAR hash for a given station
    We can skip fetching the report if geonames already returned it
    """
    ret_hash = {}
    metar = avwx.Metar(station)
    #Fetch report if one wasn't received via geonames
    if not report:
        try:
            metar.update()
        except avwx.exceptions.InvalidRequest as exc:
            return {'Error': ERRORS[0].format('METAR', station, exc)}
        except Exception as exc:
            return {'Error': ERRORS[0].format('METAR', station, exc)}
    else:
        metar.update(report)
    #Standard response
    parse_state = metar.data
    ret_hash[HASH_KEYS[1]] = deepcopy(parse_state)
    #Translate response
    parse_state['Translations'] = metar.translations
    ret_hash[HASH_KEYS[2]] = deepcopy(parse_state)
    #Summary response
    parse_state['Summary'] = metar.summary
    ret_hash[HASH_KEYS[3]] = deepcopy(parse_state)
    #Speech response
    parse_state['Speech'] = metar.speech
    ret_hash[HASH_KEYS[4]] = parse_state
    return ret_hash

def get_taf_hash(station: str) -> {str: object}:
    """Get the full TAF hash for a given station
    """
    ret_hash = {}
    taf = avwx.Taf(station)
    #Fetch new report
    try:
        taf.update()
    except avwx.exceptions.InvalidRequest as exc:
        return {'Error': ERRORS[0].format('TAF', station, exc)}
    except Exception as exc:
        return {'Error': ERRORS[0].format('TAF', station, exc)}
    #Standard response
    parse_state = taf.data
    ret_hash[HASH_KEYS[1]] = deepcopy(parse_state)
    #Translate response
    parse_state['Translations'] = taf.translations
    ret_hash[HASH_KEYS[2]] = deepcopy(parse_state)
    #Special handling for TAF summary response
    for i, forecast in enumerate(taf.translations['Forecast']):
        print(i, forecast)
        parse_state['Forecast'][i]['Summary'] = avwx.summary.taf(forecast)
    ret_hash[HASH_KEYS[3]] = parse_state
    return ret_hash

def handle_report(rtype: str, loc: [str], opts: [str]) -> {str: object}:
    """Returns weather data for the given report type, station, and options

    Uses a redis cache to store recent report hashes which are (at most) two minutes old
    """
    print(rtype, loc, opts)
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
    #Create redis key from station name and report type
    dlevel = data_level(opts)
    rkey = '{}-{}'.format(station, rtype)
    #Fetch hash from redis cache
    rserv = redis.StrictRedis(host=REDIS_CRED['host'], port=REDIS_CRED['port'], db=0,
                              password=REDIS_CRED['password'], ssl=True)
    rhash = dict(zip(HASH_KEYS, rserv.hmget(rkey, HASH_KEYS)))
    rhdt = rhash[HASH_KEYS[0]]
    #If no previous hash or the hash's timestamp is older than two minutes
    if not rhdt or str(datetime.utcnow()-timedelta(minutes=2)) > rhdt.decode('ascii'):
        #Fetch the new hash data for the given report type
        if rtype == 'metar':
            rhash = get_metar_hash(station, report)
        else:
            rhash = get_taf_hash(station)
        if 'Error' in rhash:
            return rhash
        rhash[HASH_KEYS[0]] = datetime.utcnow()
        #Send the new hash to redis
        rserv.hmset(rkey, rhash)
        rdict = rhash[dlevel]
    else:
        #Decode the binary blob into a usable dictionary
        rdict = literal_eval(rhash[dlevel].decode('ascii'))
    #Add station info if requested
    if 'info' in opts:
        rdict['Info'] = avwx.Report(station).station_info
    return rdict

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

#https://azure.microsoft.com/en-us/documentation/articles/cache-python-get-started/
#https://redis-py.readthedocs.io/en/latest/#redis.StrictRedis.hmset
