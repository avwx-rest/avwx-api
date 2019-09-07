"""
Michael duPont - michael@mdupont.com
avwx_api.cache - Class for communicating with the report cache
"""

# stdlib
import asyncio as aio
from copy import copy
from datetime import datetime, timedelta

# library
from pymongo.errors import AutoReconnect, OperationFailure


# Table expiration in minutes
EXPIRES = {"token": 15}
DEFAULT_EXPIRES = 2


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


def has_expired(time: datetime, table: str) -> bool:
    """
    Returns True if a datetime is older than the number of minutes given
    """
    if not time:
        return True
    minutes = EXPIRES.get(table, DEFAULT_EXPIRES)
    return datetime.utcnow() > time + timedelta(minutes=minutes)


async def call(op: "coroutine") -> object:
    """
    Error handling around the Mongo client conection
    """
    for _ in range(5):
        try:
            resp = await op
            return resp
        except OperationFailure:
            return
        except AutoReconnect:
            await aio.sleep(0.5)


async def get(table: str, key: str, force: bool = False) -> {str: object}:
    """
    Returns the current cached data for a report type and station or None

    By default, will only return if the cache timestamp has not been exceeded
    Can force the cache to return if force is True
    """
    from avwx_api import mdb

    if mdb is None:
        return
    op = mdb.cache[table.lower()].find_one({"_id": key})
    data = await call(op)
    data = replace_keys(data, "_$", "$")
    if force:
        return data
    elif isinstance(data, dict) and not has_expired(data.get("timestamp"), table):
        return data
    return


async def update(table: str, key: str, data: {str: object}):
    """
    Update the cache
    """
    from avwx_api import mdb

    if mdb is None:
        return
    data = replace_keys(copy(data), "$", "_$")
    data["timestamp"] = datetime.utcnow()
    op = mdb.cache[table.lower()].update_one({"_id": key}, {"$set": data}, upsert=True)
    await call(op)
    return
