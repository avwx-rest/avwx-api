"""
Michael duPont - michael@mdupont.com
avwx_api.counter - Usage counting for analytics
"""

# stdlib
import asyncio as aio
from contextlib import asynccontextmanager
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


@app.after_serving
async def clean_queue():
    """
    Cancel workers gracefully before shutdown
    """
    for worker in workers:
        worker.cancel()
    # Wait until all workers are cancelled
    await aio.gather(*workers, return_exceptions=True)


async def worker():
    """
    Task worker increments ident counters
    """
    from avwx_api import mdb

    while True:
        icao, request_type = await queue.get()
        if mdb is None:
            continue
        date = datetime.utcnow().strftime(r"%Y-%m-%d")
        await mdb.station_counter.update_one(
            {"_id": icao}, {"$inc": {f"{request_type}.{date}": 1}}, upsert=True
        )
        queue.task_done()


def increment_station(icao: str, request_type: str):
    """
    Increments a station counter
    """
    queue.put_nowait((icao, request_type))
    return


def from_params(params: "structs.Params", report_type: str):
    """
    Counts station based on param values
    """
    if hasattr(params, "station"):
        icao = params.station.icao
    elif hasattr(params, "location") and isinstance(params.location, Station):
        icao = params.location.icao
    else:
        return
    increment_station(icao, report_type)
    return
