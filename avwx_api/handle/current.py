"""
Handle current report requests
"""

# pylint: disable=arguments-differ,missing-class-docstring

# stdlib
from typing import Optional

# module
import avwx
from avwx.structs import Coord
from avwx_api.handle.base import (
    ListedReportHandler,
    ManagerHandler,
    ReportHandler,
    ERRORS,
)
from avwx_api.structs import DataStatus, ParseConfig


OPTIONS = ("summary", "speech", "translate")


class MetarHandler(ReportHandler):
    parser = avwx.Metar
    option_keys = OPTIONS


class TafHandler(ReportHandler):
    parser = avwx.Taf
    option_keys = OPTIONS


class AirSigHandler(ManagerHandler):
    parser = avwx.AirSigmet
    manager = avwx.AirSigManager


class PirepHandler(ListedReportHandler):
    parser: avwx.Pireps = avwx.Pireps
    report_type = "pirep"

    async def fetch_report(
        self,
        loc: avwx.Station | Coord,
        config: ParseConfig,
    ) -> DataStatus:
        """Returns weather data for the given report type, station, and options
        Also returns the appropriate HTTP response code

        Uses a cache to store recent report hashes which are (at most) two minutes old
        If nofail and a new report can't be fetched, the cache will be returned with a warning
        """
        station, code, cache = None, 200, None
        # If coordinates. We don't cache coordinates
        if isinstance(loc, Coord):
            parser = self.parser(coord=loc)
            data, code = await self._new_report(parser, cache=False)
        elif isinstance(loc, avwx.Station):
            station = loc
            if not station.sends_reports:
                return {"error": ERRORS[6].format(station.lookup_code)}, 204
            data, cache, code = await self._station_cache_or_fetch(station)
        else:
            raise Exception(f"loc is not a valid value: {loc}")
        return await self._post_handle(data, code, cache, station, config)

    @staticmethod
    def validate_supplied_report(report: str) -> Optional[DataStatus]:
        """Validates a report supplied by the user before parsing
        Returns a data status tuple only if an error is found"""
        if len(report) < 3 or "{" in report:
            return ({"error": "Could not find station at beginning of report"}, 400)
        if report and report[:3] in ("ARP", "ARS"):
            return (
                {"error": "The report looks like an AIREP. Use /api/airep/parse"},
                400,
            )
        return None


class NotamHandler(ListedReportHandler):
    parser = avwx.Notams
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
                return {"error": ERRORS[6].format(station.lookup_code)}, 204
            # Don't cache non-default radius
            if config.distance != 10:
                parser = self.parser(station.lookup_code)
                parser.radius = int(config.distance)
                data, code = await self._new_report(parser, cache=False)
            else:
                data, cache, code = await self._station_cache_or_fetch(station)
        else:
            raise Exception(f"loc is not a valid value: {loc}")
        return await self._post_handle(data, code, cache, station, config)
