"""
Michael duPont - michael@mdupont.com
avwx_api.cache - Class for communicating with the report cache
"""

# stdlib
import asyncio as aio
from datetime import datetime, timedelta
from os import environ
# library
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import AutoReconnect, OperationFailure
# module
from avwx_api import app

cache_db = None

@app.before_serving
def init_cache():
    mongo_uri = environ.get('MONGO_URI')
    if mongo_uri:
        global cache_db
        cache_db = AsyncIOMotorClient(mongo_uri).report_cache

def replace_keys(data: dict, key: str, by_key: str) -> dict:
    """
    Replaces recurively the keys equal to 'key' by 'by_key'

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

def has_expired(time: datetime, minutes: int = 2) -> bool:
    """
    Returns True if a datetime is older than the number of minutes given
    """
    if not time:
        return True
    return datetime.utcnow() > time + timedelta(minutes=minutes)

async def get(rtype: str, station: str, force: bool = False) -> {str: object}:
    """
    Returns the current cached data for a report type and station or None

    By default, will only return if the cache timestamp has not been exceeded
    Can force the cache to return if force is True
    """
    if not cache_db:
        return
    for i in range(5):
        try:
            data = await cache_db[rtype.lower()].find_one({'_id': station})
            data = replace_keys(data, '_$', '$')
            if force or (isinstance(data, dict) and not has_expired(data.get('timestamp'))):
                return data
        except OperationFailure:
            return
        except AutoReconnect:
            await aio.sleep(0.5)

async def update(rtype: str, data: {str: object}):
    """
    Update the cache
    """
    if not cache_db:
        return
    data = replace_keys(data, '$', '_$')
    data['timestamp'] = datetime.utcnow()
    id = data['data'].get('station')
    # Make five attempts to connect to server
    for i in range(5):
        try:
            await cache_db[rtype.lower()].update_one({'_id': id}, {'$set': data}, upsert=True)
            return
        except OperationFailure:
            return
        except AutoReconnect:
            await aio.sleep(0.5)
