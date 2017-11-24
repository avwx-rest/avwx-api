"""
Michael duPont - michael@mdupont.com
avwx_api.cache - Class for communicating with the report cache
"""

# stdlib
from datetime import datetime, timedelta
from os import environ
# library
import pymongo

MONGO_URI = environ['MONGO_URI']

class Cache(object):
    """Controls connections with the MongoDB-compatible document cache"""

    def __init__(self):
        db = pymongo.MongoClient(MONGO_URI).report_cache
        self.tables = {
            'metar': db.metar,
            'taf': db.taf
        }

    def get(self, rtype: str, station: str, not_expired: bool = True) -> {str: object}:
        """Returns the current cached data for a report type and station or None
        
        By default, will only return if the cache timestamp has not been exceeded
        """
        data = self.tables[rtype].find_one({'_id': station})
        if isinstance(data, dict) and datetime.utcnow() > data['timestamp'] + timedelta(minutes=2):
            return data

    def update(self, rtype: str, data: {str: object}):
        """Update the cache"""
        data['timestamp'] = datetime.utcnow()
        self.tables[rtype].update({'_id': data['data']['Station']}, data, upsert=True)