"""
NOTAM handling during FAA ICAO format migration
"""

import re
from datetime import date, datetime

import avwx
from avwx.exceptions import exception_intercept
from avwx.current import notam as _notam
from avwx.current.base import Reports
from avwx.static.core import IN_UNITS
from avwx.structs import Coord, NotamData, Qualifiers, Timestamp, Units

from avwx_api.service import FAA_NOTAM
from avwx_api.handle.base import ListedReportHandler, ERRORS
from avwx_api.structs import DataStatus, ParseConfig


TAG_PATTERN = re.compile(r"<[^>]*>")


def timestamp_from_notam_date(text: str) -> Timestamp | str:
    """Convert FAA NOTAM dt format"""
    if text == "PERM":
        return text
    issued_value = datetime.strptime(text, r"%m/%d/%Y %H%M")
    return Timestamp(text, issued_value)


def parse_icao_notam(report: str, issue_text: str | None) -> tuple[NotamData, Units]:
    """Parse the standard ICAO format NOTAM with the avwx class"""
    report = TAG_PATTERN.sub("", report).strip()
    issued = timestamp_from_notam_date(issue_text) if issue_text else None
    return _notam.parse(report, issued=issued)


def parse_legacy_notam(data: dict) -> tuple[NotamData, Units]:
    """Parse traditional NOTAM object from FAA API"""
    coord_text = data["mapPointer"][6:-1]
    lat, lon = coord_text.split()
    coord = Coord(float(lat), float(lon), coord_text)
    qualifiers = Qualifiers(
        repr="",
        fir="",
        subject=data["featureName"],
        condition=None,
        traffic=None,
        purpose=[],
        scope=[],
        lower=None,
        upper=None,
        coord=coord,
        radius=None,
    )
    return NotamData(
        raw=data["traditionalMessage"],
        sanitized=data["traditionalMessage"],
        station=data["icaoId"],
        time=timestamp_from_notam_date(data["issueDate"]),
        remarks=None,
        number=data["notamNumber"],
        replaces=None,
        type=None,
        qualifiers=qualifiers,
        start_time=timestamp_from_notam_date(data["startDate"]),
        end_time=timestamp_from_notam_date(data["endDate"]),
        schedule=None,
        body=data["traditionalMessage"],
        lower=None,
        upper=None,
    ), Units(**IN_UNITS)


class Notams(Reports):
    """Class to handle NOTAM reports

    This copy keeps or converts the datasource dicts for data extraction
    """

    raw: list[dict] | None = None
    data: list[NotamData] | None = None  # type: ignore
    radius: int = 10

    def __init__(self, code: str | None = None, coord: Coord | None = None):
        super().__init__(code, coord)
        self.service = FAA_NOTAM("notam")

    async def _post_update(self) -> None:
        self._post_parse()

    def _post_parse(self) -> None:
        self.data, units = [], None
        if self.raw is None:
            return
        for item in self.raw:
            try:
                if report := item.get("icaoMessage", "").strip():
                    data, units = parse_icao_notam(report, item.get("issueDate"))
                else:
                    data, units = parse_legacy_notam(item)
                self.data.append(data)
            except Exception as exc:  # pylint: disable=broad-except
                exception_intercept(exc, raw=report)  # type: ignore
        if units:
            self.units = units

    @staticmethod
    def sanitize(report: str) -> str:
        """Sanitizes a NOTAM string"""
        return _notam.sanitize(report)

    async def async_update(self, timeout: int = 10, disable_post: bool = False) -> bool:
        """Async updates report data by fetching and parsing the report"""
        reports = await self.service.async_fetch(  # type: ignore
            icao=self.code, coord=self.coord, radius=self.radius, timeout=timeout
        )
        self.source = self.service.root
        return await self._update(reports, None, disable_post)

    async def async_parse(
        self, reports: str | list[str], issued: date | None = None
    ) -> bool:
        """Async updates report data by parsing a given report

        Can accept a report issue date if not a recent report string
        """
        self.source = None
        if isinstance(reports, str):
            reports = [reports]
        reports = [{"icaoMessage": r} for r in reports]
        return await self._update(reports, issued, False)


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
        station, code, cache = None, 200, None
        # Don't cache coordinates
        if isinstance(loc, Coord):
            parser = self.parser(coord=loc)
            parser.radius = int(config.distance)
            data, code = await self._new_report(parser, cache=False)
        elif isinstance(loc, avwx.Station):
            station = loc
            if not station.sends_reports:
                return {"error": ERRORS[6].format(station.storage_code)}, 204
            # Don't cache non-default radius
            if config.distance != 10:
                parser = self.parser(station.lookup_code)
                parser.radius = int(config.distance)
                data, code = await self._new_report(parser, cache=False)
            else:
                data, cache, code = await self._station_cache_or_fetch(station)
        else:
            raise ValueError(f"loc is not a valid value: {loc}")
        return await self._post_handle(data, code, cache, station, config)
