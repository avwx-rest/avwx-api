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

    async def add(self, report_type: str, data: "ReportData"):
        """
        Add new report data to archive
        """
        if self._app.mdb and data.time and data.time.dt:
            date = data.time.dt.replace(hour=0, minute=0, second=0, microsecond=0)
            key = {"icao": data.station, "date": date}
            update = {"$set": {"raw": {data.time.repr.rstrip("Z"): data.raw}}}
            await self._app.mdb.history[report_type].update_one(
                key, update, upsert=True
            )
