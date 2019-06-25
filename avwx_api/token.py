"""
Michael duPont - michael@mdupont.com
avwx_api.token - Manages connections to work with authentication tokens
"""

# stdlib
from datetime import datetime
from os import environ
from ssl import SSLContext

# library
import asyncpg
from pymongo import UpdateOne

# module
from avwx_api import cache


PSQL_URI = environ.get("PSQL_URI", None)
TOKEN_QUERY = "SELECT active_token, plan FROM public.user WHERE apitoken = '{}'"


LIMITS = {"basic": None, "enterprise": None}


async def _get_token_data(token: str) -> dict:
    """
    Returns data for a token value
    """
    conn = await asyncpg.connect(PSQL_URI, ssl=SSLContext())
    result = await conn.fetch(TOKEN_QUERY.format(token))
    await conn.close()
    if not result:
        return
    return result[0]


async def increment_token(token: str, maxv: int = None) -> bool:
    """
    Increments a token value in the counter

    Returns True if the token has hit its daily limit
    """
    from avwx_api import mdb

    if mdb is None:
        return False
    key = datetime.utcnow().strftime(r"%Y-%m-%d")
    # Create or increment the date counter
    ops = [UpdateOne({"_id": token}, {"$inc": {key: 1}}, upsert=True)]
    # Reset counter to max if at or exceeded max value
    if maxv is not None:
        ops.append(
            UpdateOne({"_id": token, key: {"$gte": maxv}}, {"$set": {key: maxv}})
        )
    op = mdb.token_counter.bulk_write(ops)
    r = await cache.call(op)
    # Limit met if both operations modified the object
    return r.modified_count > 1


async def get_token(token: str) -> dict:
    """
    Returns account data associated with token value
    """
    data = await cache.get("token", token)
    if not data:
        data = await _get_token_data(token)
        if data:
            await cache.update("token", token, dict(data))
    return data
