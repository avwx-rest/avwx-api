"""
Manages report archive population
"""

# stdlib
from dataclasses import asdict

# module
from avwx_api_core.util.queue import Queue


class HistoryQueue:
    """
    Adds new data into the report archive
    """

    _app: "Quart"
    _queue: Queue

    def __init__(self, app: "Quart"):
        self._app = app
        self._queue = Queue(self)
        self._app.after_serving(self._queue.clean)

    @staticmethod
    def make_key(data: "ReportData") -> str:
        """
        Create the document key from the report data
        """
        date = data.time.dt
        key = data.time.repr.rstrip("Z")
        return f"{date.year}.{date.month}.{date.day}.{key}"

    async def _worker(self):
        """
        Task worker increments ident counters
        """
        while True:
            async with self._queue.get() as value:
                if self._app.mdb:
                    report_type, data = value
                    await self._app.mdb.history[report_type].update_one(
                        {"_id": data.station},
                        {"$set": {self.make_key(data): asdict(data)}},
                        upsert=True,
                    )

    def add(self, report_type: str, data: "ReportData"):
        """
        Add new report data to archive
        """
        self._queue.add((report_type, data))
