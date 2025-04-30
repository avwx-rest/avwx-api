"""NOTAM handling during FAA ICAO format migration."""

from datetime import date, datetime, timezone
from http import HTTPStatus

import avwx
from avwx.current import notam as _notam
from avwx.current.base import Reports
from avwx.exceptions import exception_intercept
from avwx.static.core import IN_UNITS
from avwx.structs import Coord, NotamData, Timestamp, Units

from avwx_api.handle.base import ERRORS, ListedReportHandler
from avwx_api.service import FaaDinsNotam
from avwx_api.structs import DataStatus, ParseConfig


def _convert_time(text: str) -> Timestamp | None:
    """Convert 04 MAR 13:00 2025 to Timestamp"""
    if not text:
        return None
    if text.startswith("PERM"):
        return Timestamp(text, datetime(2100, 1, 1, tzinfo=timezone.utc))
    return Timestamp(text, datetime.strptime(text, r"%d %b %H:%M %Y"))  # noqa: DTZ007


def _extract_number(report: str) -> tuple[str, str]:
    """Extract the NOTAM number from the report"""
    start = report.find(" - ")
    return report[start + 3 :], report[:start]


def _extract_timestamps(report: str) -> tuple[str, Timestamp, Timestamp]:
    """Extract the start and end timestamps from the report"""
    time_start = report.rfind(". ")
    times = report[time_start + 2 :]
    report = report[:time_start]
    times = times.removesuffix(" ESTIMATED")
    start, end = times.split(" UNTIL ")
    time_start = start.rfind(", ")
    if time_start > -1:
        start = start[time_start + 2 :]
    return report, _convert_time(start), _convert_time(end)


def temp_parse_notam(report: str) -> tuple[NotamData, Units]:
    """Parse the standard ICAO format NOTAM with the avwx class"""
    station, body = report[:4], report[5:]
    body, issued = body.split(". CREATED: ")
    body, number = _extract_number(body)
    body, start, end = _extract_timestamps(body)
    return NotamData(
        raw=report,
        sanitized=report,
        station=station,
        time=_convert_time(issued),
        remarks=None,
        number=number,
        replaces=None,
        type=None,
        qualifiers=None,
        start_time=start,
        end_time=end,
        schedule=None,
        body=body,
        lower=None,
        upper=None,
    ), Units(**IN_UNITS)


class Notams(Reports):
    """Class to handle NOTAM reports."""

    data: list[NotamData] | None = None  # type: ignore
    radius: int = 10

    def __init__(self, code: str | None = None, coord: Coord | None = None):
        super().__init__(code, coord)
        self.service = FaaDinsNotam("notam")

    async def _post_update(self) -> None:
        self._post_parse()

    def _post_parse(self) -> None:
        self.data, units = [], None
        if self.raw is None:
            return
        for report in self.raw:
            try:
                data, units = temp_parse_notam(report)
                self.data.append(data)
            except Exception as exc:  # noqa: BLE001
                exception_intercept(exc, raw=report)  # type: ignore
        if units:
            self.units = units

    @staticmethod
    def sanitize(report: str) -> str:
        """Sanitizes a NOTAM string"""
        return _notam.sanitize(report)

    async def async_update(self, timeout: int = 10, *, disable_post: bool = False) -> bool:
        """Async updates report data by fetching and parsing the report"""
        reports = await self.service.async_fetch(  # type: ignore
            icao=self.code, coord=self.coord, radius=self.radius, timeout=timeout
        )
        self.source = self.service.root
        return await self._update(reports, None, disable_post=disable_post)

    async def async_parse(self, reports: str | list[str], issued: date | None = None) -> bool:
        """Async updates report data by parsing a given report

        Can accept a report issue date if not a recent report string
        """
        self.source = None
        if isinstance(reports, str):
            reports = [reports]
        return await self._update(reports, issued, disable_post=False)


class NotamHandler(ListedReportHandler):
    parser = Notams
    report_type = "notam"

    async def fetch_report(
        self,
        loc: avwx.Station | Coord,
        config: ParseConfig,
    ) -> DataStatus:
        """Returns NOTAMs for a location and config

        Caching only applies to stations with default radius, not coord or custom radius
        """
        station, code, cache = None, HTTPStatus.OK, None
        # Don't cache coordinates
        if isinstance(loc, Coord):
            parser = self.parser(coord=loc)
            if config.distance:
                parser.radius = int(config.distance)
            data, code = await self._new_report(parser, cache=False)
        elif isinstance(loc, avwx.Station):
            station = loc
            if not station.sends_reports:
                return {"error": ERRORS[6].format(station.storage_code)}, HTTPStatus.NO_CONTENT
            # Don't cache non-default radius
            if config.distance and config.distance != 10:
                parser = self.parser(station.lookup_code)
                parser.radius = int(config.distance)
                data, code = await self._new_report(parser, cache=False)
            else:
                data, cache, code = await self._station_cache_or_fetch(station)
        else:
            msg = f"loc is not a valid value: {loc}"
            raise TypeError(msg)
        return await self._post_handle(data, code, cache, station, config)
