"""
Michael duPont - michael@mdupont.com
avwx_api.token - Manages connections to work with authentication tokens
"""

# stdlib
import asyncio as aio
from os import environ
# library
import asyncpg

PSQL_URI = environ.get('PSQL_URI', None)
TOKEN_QUERY = "SELECT active_token, plan FROM public.user WHERE apitoken = '{}'"

async def validate_token(token: str) -> bool:
    """
    Returns whether or not a given token is valid and active
    """
    if not PSQL_URI:
        return True
    conn = await asyncpg.connect(PSQL_URI)
    result = await conn.fetch(TOKEN_QUERY.format(token))
    await conn.close()
    if not result:
        return False
    return result[0]['active_token']
