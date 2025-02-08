"""Notam service"""


import asyncio as aio
import json
from typing import Any

import rollbar
from avwx.exceptions import InvalidRequest
from avwx.service.scrape import ScrapeService
from avwx.structs import Coord

# Copy of the NOTAM service to return all available data.
# This can be removed in the future once ICAO NOTAM format is more widely available.

# Search fields https://notams.aim.faa.gov/NOTAM_Search_User_Guide_V33.pdf


class FAA_NOTAM(ScrapeService):
    """Sources NOTAMs from official FAA portal"""

    url = "https://notams.aim.faa.gov/notamSearch/search"
    method = "POST"
    _valid_types = ("notam",)

    @staticmethod
    def _make_headers() -> dict:
        return {"Content-Type": "application/x-www-form-urlencoded"}

    @staticmethod
    def _split_coord(prefix: str, value: float) -> dict:
        """Adds coordinate deg/min/sec fields per float value"""
        degree, minute, second = Coord.to_dms(value)
        if prefix == "lat":
            key = "latitude"
            direction = "N" if degree >= 0 else "S"
        else:
            key = "longitude"
            direction = "E" if degree >= 0 else "W"
        return {
            f"{prefix}Degrees": abs(degree),
            f"{prefix}Minutes": minute,
            f"{prefix}Seconds": second,
            f"{key}Direction": direction,
        }

    def _post_for(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
    ) -> dict:
        """Generate POST payload for search params in location order"""
        data: dict[str, Any] = {"notamsOnly": False, "radius": radius}
        if icao:
            data["searchType"] = 0
            data["designatorsForLocation"] = icao
        elif coord:
            data["searchType"] = 3
            data["radiusSearchOnDesignator"] = False
            data |= self._split_coord("lat", coord.lat)
            data |= self._split_coord("long", coord.lon)
        elif path:
            data["searchType"] = 6
            data["flightPathText"] = " ".join(path)
            data["flightPathBuffer"] = radius
            data["flightPathIncludeNavaids"] = True
            data["flightPathIncludeArtcc"] = False
            data["flightPathIncludeTfr"] = True
            data["flightPathIncludeRegulatory"] = False
            data["flightPathResultsType"] = "All NOTAMs"
        else:
            raise InvalidRequest("Not enough info to request NOTAM data")
        return data

    def fetch(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
        timeout: int = 10,
    ) -> list[str]:
        """Fetch NOTAM list from the service via ICAO, coordinate, or ident path"""
        return aio.run(self.async_fetch(icao, coord, path, radius, timeout))

    async def async_fetch(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
        timeout: int = 10,
    ) -> list[dict]:
        """Async fetch NOTAM list from the service via ICAO, coordinate, or ident path"""
        headers = self._make_headers()
        data = self._post_for(icao, coord, path, radius)
        notams = []
        while True:
            text = await self._call(self.url, None, headers, data, timeout)
            try:
                resp: dict = json.loads(text)
            except json.JSONDecodeError as exc:
                fields = {"text": text, "icao": icao, "coord": coord.pair, "path": path, "radius": radius}
                rollbar.report_exc_info(exc, extra_data=fields)
                raise self._make_err("Failed to decode JSON response. The admin has been notified of the issue")
            if resp.get("error"):
                raise self._make_err("Search criteria appears to be invalid")
            notams += resp["notamList"]
            offset = resp["endRecordCount"]
            if not notams or offset >= resp["totalNotamCount"]:
                break
            data["offset"] = offset
        return notams
