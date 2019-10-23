"""
Michael duPont - michael@mdupont.com
avwx_api.counter - Usage counting for analytics
"""

# stdlib
import asyncio as aio
import time
from datetime import datetime

# library
from avwx import Station

# module
from avwx_api import app


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


async def worker():
    """
    Task worker increments ident counters
    """
    from avwx_api import mdb

    while True:
        icao, request_type, count = await queue.get()
        if mdb is None:
            continue
        date = datetime.utcnow().strftime(r"%Y-%m-%d")
        await mdb.counter.station.update_one(
            {"_id": icao}, {"$inc": {f"{request_type}.{date}": count}}, upsert=True
        )
        queue.task_done()


class DelayedCounter:
    """
    Manages station counts to limit calls to database
    """

    _data: dict
    update_at: int
    interval: int  # seconds
    locked: bool = False

    def __init__(self, interval: int = 60):
        self._data = {}
        self.interval = interval
        self.update_at = time.time() + self.interval

    def gather_data(self) -> dict:
        """
        Returns existing data while locking to prevent missed values
        """
        self.locked = True
        to_update = self._data
        self._data = {}
        self.locked = False
        return to_update

    def update(self):
        """
        Sends station counts to worker queue
        """
        to_update = self.gather_data()
        for key, count in to_update.items():
            icao, request_type = key.split(";")
            queue.put_nowait((icao, request_type, count))
        self.update_at = time.time() + self.interval

    async def add(self, icao: str, request_type: str):
        """
        Increment the counter for a station and type
        """
        if time.time() > self.update_at:
            self.update()
        while self.locked:
            await aio.sleep(0.000001)
        key = f"{icao};{request_type}"
        try:
            self._data[key] += 1
        except KeyError:
            self._data[key] = 1


_COUNTER = DelayedCounter()


async def increment_station(icao: str, request_type: str):
    """
    Increments a station counter
    """
    await _COUNTER.add(icao, request_type)


async def from_params(params: "structs.Params", report_type: str):
    """
    Counts station based on param values
    """
    if hasattr(params, "station"):
        icao = params.station.icao
    elif hasattr(params, "location") and isinstance(params.location, Station):
        icao = params.location.icao
    else:
        return
    await increment_station(icao, report_type)


@app.after_serving
async def clean_queue():
    """
    Cancel workers gracefully before shutdown
    """
    if queue is None:
        return
    # Clean out the counter first
    _COUNTER.update()
    while not queue.empty():
        await aio.sleep(0.01)
    for worker in workers:
        worker.cancel()
    # Wait until all workers are cancelled
    await aio.gather(*workers, return_exceptions=True)
