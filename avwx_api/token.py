"""
Michael duPont - michael@mdupont.com
avwx_api.token - Manages connections to work with authentication tokens
"""

# stdlib
from dataclasses import dataclass
from datetime import datetime
from os import environ
from ssl import SSLContext

# library
import asyncpg
from pymongo import UpdateOne

# module
from avwx_api import app, cache


PSQL_URI = environ.get("PSQL_URI", None)
TOKEN_QUERY = """
SELECT u.active_token AS active, p.limit, p.name, p.type
FROM public.user u
JOIN public.plan p 
ON u.plan_id = p.id
WHERE apitoken = '{}';
"""


PSQL_CONN = None


@app.before_first_request
async def init_conn():
    """
    Create the connection to the account database
    """
    if not PSQL_URI:
        return
    global PSQL_CONN
    if "localhost" in PSQL_URI:
        PSQL_CONN = await asyncpg.connect(PSQL_URI)
    else:
        PSQL_CONN = await asyncpg.connect(PSQL_URI, ssl=SSLContext())


@app.after_serving
async def close_conn():
    """
    Close connection to the account database
    """
    if PSQL_CONN:
        await PSQL_CONN.close()


@dataclass
class Token:
    """
    Client auth token
    """

    active: bool
    limit: int
    name: str
    type: str
    value: str

    @classmethod
    async def from_token(cls, token: str) -> "Token":
        """
        Returns account data associated with token value
        """
        data = await cache.get("token", token)
        if data:
            # Remove cache meta
            del data["_id"]
            del data["timestamp"]
        else:
            result = await PSQL_CONN.fetch(TOKEN_QUERY.format(token))
            if not result:
                return
            data = dict(result[0])
            await cache.update("token", token, data)
        return cls(value=token, **data)

    @property
    def is_paid(self) -> bool:
        """
        Returns if a token is an active paid token
        """
        return self.active and self.type == "paid"

    def valid_type(self, types: [str]) -> bool:
        """
        Returns True if an active token matches one of the plan types
        """
        return self.active and self.type in types

    async def increment(self):
        """
        Increments a token value in the counter

        Returns True if the token has hit its daily limit
        """
        from avwx_api import mdb

        if mdb is None:
            return False
        key = datetime.utcnow().strftime(r"%Y-%m-%d")
        # Create or increment the date counter
        ops = [UpdateOne({"_id": self.value}, {"$inc": {key: 1}}, upsert=True)]
        # Reset counter to max if at or exceeded max value
        if self.limit is not None:
            ops.append(
                UpdateOne(
                    {"_id": self.value, key: {"$gte": self.limit}},
                    {"$set": {key: self.limit}},
                )
            )
        op = mdb.counter.token.bulk_write(ops)
        r = await cache.call(op)
        # Limit met if both operations modified the object
        return r.modified_count > 1
