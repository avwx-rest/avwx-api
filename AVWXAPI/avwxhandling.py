#!/usr/bin/python3

"""
Data handling between inputs, redis, and avwx function library

Requires credentials.py
REDIS_CRED = {
    'host': 'redis_host_url',
    'password': 'redis_pw'
}
GN_USER = 'geonames_username'
"""

# pylint: disable=E1101,W0703

#stdlib
from ast import literal_eval
from copy import deepcopy
from datetime import datetime, timedelta
#library
import redis
from requests import get
#module
from .avwx import getMETAR, getTAF, parseMETAR, parseTAF, translateMETAR, translateTAF, \
                  createMETARSummary, createTAFLineSummary, getInfoForStation
from .credentials import GN_USER, REDIS_CRED

COORD_URL = 'http://api.geonames.org/findNearByWeatherJSON?lat={}&lng={}&username=' + GN_USER
HASH_KEYS = ('timestamp', 'standard', 'translate', 'summary')

ERRORS = [
    'Station Lookup Error: {} not found for {} ({})'
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
    """Returns data level key depending on values in options
    """
    for key in HASH_KEYS[1:]:
        if key in opts:
            return key
    return HASH_KEYS[1]

def get_metar_hash(station: str, report: str) -> {str: object}:
    """Get the full METAR hash for a given station
    We can skip fetching the report if geonames already returned it
    """
    ret_hash = {}
    #Fetch report if one wasn't received via geonames
    if not report:
        report = getMETAR(station)
    if isinstance(report, int):
        return {'Error': ERRORS[0].format('METAR', station, report)}
    #Standard response
    parse_state = parseMETAR(report.strip())
    ret_hash[HASH_KEYS[1]] = deepcopy(parse_state)
    #Translate response
    parse_state['Translations'] = translateMETAR(parse_state)
    ret_hash[HASH_KEYS[2]] = deepcopy(parse_state)
    #Summary response
    parse_state['Summary'] = createMETARSummary(parse_state['Translations'])
    ret_hash[HASH_KEYS[3]] = parse_state
    return ret_hash

def get_taf_hash(station: str) -> {str: object}:
    """Get the full TAF hash for a given station
    """
    ret_hash = {}
    #Fetch new report
    report = getTAF(station)
    if isinstance(report, int):
        return {'Error': ERRORS[0].format('TAF', station, report)}
    #Standard response
    parse_state = parseTAF(report.strip())
    ret_hash[HASH_KEYS[1]] = deepcopy(parse_state)
    #Translate response
    trans = translateTAF(parse_state)
    parse_state['Translations'] = trans
    ret_hash[HASH_KEYS[2]] = deepcopy(parse_state)
    #Special handling for TAF summary response
    for i in range(len(trans['Forecast'])):
        parse_state['Forecast'][i]['Summary'] = createTAFLineSummary(trans['Forecast'][i])
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
        station = loc[0]
        report = None
    #Create redis key from station name and report type
    dlevel = data_level(opts)
    rkey = '{}-{}'.format(station, rtype)
    #Fetch hash from redis cache
    rserv = redis.StrictRedis(host=REDIS_CRED['host'], port=6380, db=0,
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
        ret_dict = rhash[dlevel]
    else:
        #Decode the binary blob into a usable dictionary
        ret_dict = literal_eval(rhash[dlevel].decode('ascii'))
    #Add station info if requested
    if 'info' in opts:
        ret_dict['Info'] = getInfoForStation(station)
    return ret_dict


#https://azure.microsoft.com/en-us/documentation/articles/cache-python-get-started/
#https://redis-py.readthedocs.io/en/latest/#redis.StrictRedis.hmset
