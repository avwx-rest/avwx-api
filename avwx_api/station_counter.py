"""
Manages station counts for usage metrics
"""

# pylint: disable=arguments-differ

# stdlib
import time
from datetime import datetime, timezone

# module
from avwx_api_core.counter.base import DelayedCounter
from avwx import Station
from avwx_api.structs import Params


class StationCounter(DelayedCounter):
    """Aggregates station and method counts"""

    async def _worker(self):
        """Task worker increments ident counters"""
        while True:
            async with self._queue.get() as value:
                if self._app.mdb:
                    icao, request_type, count = value
                    date = datetime.now(tz=timezone.utc)
                    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                    await self._app.mdb.counter.station.update_one(
                        {"icao": icao, "date": date},
                        {"$inc": {request_type: count}},
                        upsert=True,
                    )

    def update(self):
        """Sends station counts to worker queue"""
        to_update = self.gather_data()
        for key, count in to_update.items():
            icao, request_type = key.split(";")
            self._queue.add((icao, request_type, count))
        self.update_at = time.time() + self.interval

    def _increment(self, icao: str, request_type: str):
        key = f"{icao};{request_type}"
        try:
            self._data[key] += 1
        except KeyError:
            self._data[key] = 1

    async def add(self, icao: str, request_type: str):
        """Increment the counter for a station and type"""
        await self._pre_add()
        self._increment(icao, request_type)

    async def add_many(self, icaos: list[str], request_type: str):
        """Increment the counts for a list of stations"""
        await self._pre_add()
        for icao in icaos:
            self._increment(icao, request_type)

    async def from_params(self, params: Params, report_type: str):
        """Counts station based on param values"""
        if hasattr(params, "station"):
            icao = params.station.icao
        elif hasattr(params, "location") and isinstance(params.location, Station):
            icao = params.location.icao
        else:
            return
        await self.add(icao, report_type)
