"""
Michael duPont - michael@mdupont.com
avwx_api.cache - Class for communicating with the report cache
"""

# stdlib
from datetime import datetime, timedelta
from os import environ
# library
import pymongo

MONGO_URI = environ.get('MONGO_URI', None)

def replace_keys(data: dict, key: str, by_key: str) -> dict:
    """Replaces recurively the keys equal to 'key' by 'by_key'

    Some keys in the report data are '$' and this is not accepted by mongodb
    """
    if data is None:
        return
    for k, v in data.items():
        if k == key:
            data[by_key] = data.pop(key)
        if isinstance(v, dict):
            data[k] = replace_keys(v, key, by_key)
    return data

class Cache(object):
    """Controls connections with the MongoDB-compatible document cache"""

    def __init__(self):
        if not MONGO_URI:
            return
        db = pymongo.MongoClient(MONGO_URI).report_cache
        self.tables = {
            'metar': db.metar,
            'taf': db.taf
        }

    @staticmethod
    def has_expired(time: datetime, minutes: int = 2) -> bool:
        """Returns True if a datetime is older than the number of minutes given"""
        return datetime.utcnow() > time + timedelta(minutes=minutes)

    def get(self, rtype: str, station: str, force: bool = False) -> {str: object}:
        """Returns the current cached data for a report type and station or None

        By default, will only return if the cache timestamp has not been exceeded
        Can force the cache to return if force is True
        """
        if not MONGO_URI:
            return
        data = self.tables[rtype].find_one({'_id': station})
        data = replace_keys(data, '_$', '$')
        if force or (isinstance(data, dict) and not self.has_expired(data['timestamp'])):
            return data

    def update(self, rtype: str, data: {str: object}):
        """Update the cache"""
        if not MONGO_URI:
            return
        data = replace_keys(data, '$', '_$')
        data['timestamp'] = datetime.utcnow()
        self.tables[rtype].update({'_id': data['data']['Station']}, data, upsert=True)
