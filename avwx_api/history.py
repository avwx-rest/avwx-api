"""
Manages report archive population
"""

# stdlib
from dataclasses import asdict


class History:
    """
    Adds new data into the report archive
    """

    _app: "Quart"

    def __init__(self, app: "Quart"):
        self._app = app

    @staticmethod
    def make_key(data: "ReportData") -> str:
        """
        Create the document key from the report data
        """
        date = data.time.dt
        key = data.time.repr.rstrip("Z")
        return f"{date.year}.{date.month}.{date.day}.{key}"

    async def add(self, report_type: str, data: "ReportData"):
        """
        Add new report data to archive
        """
        if self._app.mdb and data.time and data.time.dt:
            await self._app.mdb.history[report_type].update_one(
                {"_id": data.station},
                {"$set": {self.make_key(data): asdict(data)}},
                upsert=True,
            )
