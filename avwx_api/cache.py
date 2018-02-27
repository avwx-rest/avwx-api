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

    @staticmethod
    def replace_keys(in_dict, key, by_key):
        """ Replaces recurively the keys equal to 'key' by 'by_key' 

        Some keys in the METAR are '$' and this is not accepted by mongodb
        """    
        
        if in_dict is None:
            return

        for k, v in in_dict.items():
            if k == key:
                print("Replacing {} by {}".format(key, by_key))
                in_dict[by_key] = in_dict.pop(key)
            if isinstance(v, dict):
                Cache.replace_keys(v, key, by_key)        

    def get(self, rtype: str, station: str, force: bool = False) -> {str: object}:
        """Returns the current cached data for a report type and station or None

        By default, will only return if the cache timestamp has not been exceeded
        Can force the cache to return if force is True
        """
        if not MONGO_URI:
            return
        data = self.tables[rtype].find_one({'_id': station})

        Cache.replace_keys(data, '_$', '$')

        if force or (isinstance(data, dict) and not self.has_expired(data['timestamp'])):
            return data

    def update(self, rtype: str, data: {str: object}):
        """Update the cache"""
        if not MONGO_URI:
            return
        data['timestamp'] = datetime.utcnow()

        Cache.replace_keys(data, '$', '_$')

        self.tables[rtype].update({'_id': data['data']['Station']}, data, upsert=True)
