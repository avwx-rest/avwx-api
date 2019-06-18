"""
Michael duPont - michael@mdupont.com
avwx_api.token - Manages connections to work with authentication tokens
"""

# stdlib
import asyncio as aio
from os import environ
from ssl import SSLContext

# library
import asyncpg

# module
from avwx_api import cache


PSQL_URI = environ.get("PSQL_URI", None)
TOKEN_QUERY = "SELECT active_token, plan FROM public.user WHERE apitoken = '{}'"


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


async def validate_token(token: str) -> bool:
    """
    Returns whether or not a given token is valid and active
    """
    # Check cache for token
    data = await cache.get("token", token)
    if data:
        return True
    # Fetch token
    data = await _get_token_data(token)
    if not (data and data["active_token"]):
        return False
    # Update cache
    await cache.update("token", token, dict(data))
    return True
