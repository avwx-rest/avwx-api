"""NOTAM services."""

import asyncio as aio
import json
import re
from typing import Any

import rollbar
from avwx.exceptions import InvalidRequest
from avwx.service.scrape import ScrapeService
from avwx.structs import Coord

# Copy of the NOTAM service to return all available data.
# This can be removed in the future once ICAO NOTAM format is more widely available.

# Search fields https://notams.aim.faa.gov/NOTAM_Search_User_Guide_V33.pdf


TAG_PATTERN = re.compile(r"<[^>]*>")


class _FaaNotam(ScrapeService):
    """Sources NOTAMs from FAA portals"""

    method = "POST"
    _valid_types = ("notam",)

    def _post_for(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
    ) -> dict:
        """Generate POST payload for search params in location order"""
        raise NotImplementedError

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
    ) -> list[str]:
        """Async fetch NOTAM list from the service via ICAO, coordinate, or ident path"""
        raise NotImplementedError


class FaaNotam(_FaaNotam):
    """Sources NOTAMs from official FAA portal"""

    url = "https://notams.aim.faa.gov/notamSearch/search"

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
            msg = "Not enough info to request NOTAM data"
            raise InvalidRequest(msg)
        return data

    async def async_fetch(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
        timeout: int = 10,
    ) -> list[str]:
        """Async fetch NOTAM list from the service via ICAO, coordinate, or ident path"""
        headers = self._make_headers()
        data = self._post_for(icao, coord, path, radius)
        notams: list[str] = []
        while True:
            text = await self._call(self.url, None, headers, data, timeout)
            try:
                resp: dict = json.loads(text)
            except json.JSONDecodeError as exc:
                fields = {"text": text, "icao": icao, "coord": str(coord), "path": path, "radius": radius}
                rollbar.report_exc_info(exc, extra_data=fields)
                msg = "Failed to decode JSON response. The admin has been notified of the issue"
                raise self._make_err(msg) from exc
            if resp.get("error"):
                msg = "Search criteria appears to be invalid"
                raise self._make_err(msg)
            notams += resp["notamList"]
            offset = resp["endRecordCount"]
            if not notams or offset >= resp["totalNotamCount"]:
                break
            data["offset"] = offset
        return notams


class FaaDinsNotam(_FaaNotam):
    """Secondary NOTAM source from FAA DINS"""

    url = "https://www.notams.faa.gov/dinsQueryWeb/{}SearchMapAction.do"

    def _url_post_for(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
    ) -> tuple[str, dict]:
        """Generate URL and POST payload for search params in location order"""
        url: str
        data: dict[str, Any] = {}
        if icao:
            url = self.url.format("icaoRadius")
            data["actionType"] = "radiusSearch"
            data["geoIcaoLocId"] = icao
            data["geoIcaoRadius"] = radius
        elif coord:
            url = self.url.format("latLongRadius")
            lat_degree, lat_minute, _ = Coord.to_dms(coord.lat)
            lon_degree, lon_minute, _ = Coord.to_dms(coord.lon)
            data["actionType"] = "latLongSearch"
            data["geoLatDegree"] = abs(lat_degree)
            data["geoLatMinute"] = lat_minute
            data["geoLatNorthSouth"] = "N" if coord.lat >= 0 else "S"
            data["geoLongDegree"] = abs(lon_degree)
            data["geoLongMinute"] = lon_minute
            data["geoLongEastWest"] = "E" if coord.lon >= 0 else "W"
            data["geoLatLongRadius"] = radius
        elif path:
            if not 1 < len(path) < 6:
                msg = "Flight path must have between 2 and 5 waypoints"
                raise InvalidRequest(msg)
            url = self.url.format("flightPath")
            data["actionType"] = "flightPathSearch"
            data["geoFlightPathbuffer"] = radius
            data["geoFlightPathOptionsCT"] = "C"
            data["geoFlightPathOptionsAR"] = "A"
            for i, code in enumerate(path + [None] * (5 - len(path))):
                data[f"geoFlightPathIcao{i+1}"] = code
        else:
            msg = "Not enough info to request NOTAM data"
            raise InvalidRequest(msg)
        return url, data

    async def async_fetch(
        self,
        icao: str | None = None,
        coord: Coord | None = None,
        path: list[str] | None = None,
        radius: int = 10,
        timeout: int = 10,
    ) -> list[str]:
        """Async fetch NOTAM list from the service via ICAO, coordinate, or ident path"""
        url, data = self._url_post_for(icao, coord, path, radius)
        notams = []
        text = await self._call(url, data=data, timeout=timeout)
        sections = text.split('<TD nowrap class="textBlack12Bu" width="370" valign="top"><A')
        sections.pop(0)
        for section in sections:
            station_start = section.find('name="')
            station = section[station_start + 6 : station_start + 10]
            snippets = section.split('<TD class="textBlack12" valign="top"><PRE>')
            snippets.pop(0)
            for snippet in snippets:
                report = snippet[3 : snippet.find("</PRE>")].strip().upper()
                report = report.replace("\n", " ").replace("... ", "...")
                report = TAG_PATTERN.sub("", report).strip()
                notams.append(f"{station} {report}")
        return notams
