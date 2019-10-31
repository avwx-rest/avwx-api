"""
Michael duPont - michael@mdupont.com
avwx_api.token - Manages connections to work with authentication tokens
"""

# stdlib
import time
import asyncio as aio
from dataclasses import dataclass
from datetime import datetime
from os import environ
from ssl import SSLContext

# library
import asyncpg

# module
from avwx_api import app, cache
from avwx_api.counter import DelayedCounter


PSQL_URI = environ.get("PSQL_URI", None)
TOKEN_QUERY = """
SELECT u.id AS user, u.active_token AS active, p.limit, p.name, p.type
FROM public.user u
JOIN public.plan p 
ON u.plan_id = p.id
WHERE apitoken = $1;
"""


PSQL_POOL = None
MIN_SIZE = 3
MAX_SIZE = 8
TIMEOUT = 5


@app.before_serving
async def init_conn():
    """
    Create the connection to the account database
    """
    if not PSQL_URI:
        return
    kwargs = {"min_size": MIN_SIZE, "max_size": MAX_SIZE, "command_timeout": TIMEOUT}
    if "localhost" not in PSQL_URI:
        kwargs["ssl"] = SSLContext()
    global PSQL_POOL
    PSQL_POOL = await asyncpg.create_pool(PSQL_URI, **kwargs)


queue = None
workers = []


@app.before_first_request
def init_queue():
    """
    Create the counting queue and workers
    """
    global queue
    queue = aio.Queue()
    for _ in range(3):
        workers.append(aio.create_task(worker()))


def date_key() -> str:
    """
    Returns the current date as a sub POSIX key
    """
    return datetime.utcnow().strftime(r"%Y-%m-%d")


async def worker():
    """
    Task worker increments ident counters
    """
    from avwx_api import mdb

    while True:
        user, count = await queue.get()
        if mdb:
            await mdb.counter.token.update_one(
                {"_id": user}, {"$inc": {date_key(): count}}, upsert=True
            )
        queue.task_done()


async def _fetch_token_data(token: str) -> dict:
    """
    Fetch token data from the cache or primary database
    """
    data = await cache.get("token", token)
    if data:
        # Remove cache meta
        del data["_id"]
        del data["timestamp"]
    else:
        async with PSQL_POOL.acquire() as conn:
            async with conn.transaction():
                result = await conn.fetch(TOKEN_QUERY, token)
        if not result:
            return
        data = dict(result[0])
        await cache.update("token", token, data)
    return data


async def _fetch_token_usage(user: int) -> int:
    """
    Fetch current token usage from counting table
    """
    from avwx_api import mdb

    if mdb is None:
        return

    key = date_key()
    op = mdb.counter.token.find_one({"_id": user}, {"_id": 0, key: 1})
    data = await cache.call(op)
    if not data:
        return 0
    return data.get(key, 0)


class TokenCountCache(DelayedCounter):
    """
    Caches and counts user auth tokens
    """

    # NOTE: The user triggering the update will not have the correct total.
    # This means that the cutoff time is at most 2 * self.interval
    def update(self):
        """
        Sends token counts to worker queue
        """
        to_update = self.gather_data()
        for item in to_update.values():
            if not item:
                continue
            queue.put_nowait((item["data"]["user"], item["count"]))
        self.update_at = time.time() + self.interval

    async def get(self, token: str) -> dict:
        """
        Fetch data for a token. Must be called before increment
        """
        await self._pre_add()
        try:
            # Wait for busy thread to add data if not finished fetching
            item = self._data[token]
            while item is None:
                await aio.sleep(0.0001)
                item = self._data[token]
            return item["data"]
        except KeyError:
            # Set None to indicate data fetch in progress
            self._data[token] = None
            data = await _fetch_token_data(token)
            if not data:
                try:
                    del self._data[token]
                except KeyError:
                    pass
                return
            total = await _fetch_token_usage(data["user"])
            self._data[token] = {"data": data, "count": 0, "total": total}
            return data

    async def add(self, token: str) -> bool:
        """
        Increment a token usage counter
        
        Returns False if token has hit its limit or not found
        """
        try:
            self._data[token]["count"] += 1
            item = self._data[token]
            limit = item["data"]["limit"]
            if limit is None:
                return True
            return limit >= item["total"] + item["count"]
        except KeyError:
            return False


_COUNTER = TokenCountCache()


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
    user: int

    @classmethod
    async def from_token(cls, token: str) -> "Token":
        """
        Returns account data associated with token value
        """
        data = await _COUNTER.get(token)
        return cls(value=token, **data) if data else None

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

    async def increment(self) -> bool:
        """
        Increments a token value in the counter

        Returns False if the token has hit its daily limit
        """
        return await _COUNTER.add(self.value)


@app.after_serving
async def close_conn():
    """
    Close connection to the account database
    """
    if PSQL_POOL:
        await PSQL_POOL.close()


@app.after_serving
async def clean_queue():
    """
    Clear cache and cancel workers gracefully before shutdown
    """
    if queue is None:
        return
    # Clean out the counter first
    _COUNTER.update()
    while not queue.empty():
        await aio.sleep(0.01)
    for worker_thread in workers:
        worker_thread.cancel()
    # Wait until all workers are cancelled
    await aio.gather(*workers, return_exceptions=True)
