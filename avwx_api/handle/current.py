"""
Handle current report requests
"""

# pylint: disable=arguments-differ,missing-class-docstring

# stdlib
from dataclasses import asdict
from typing import Union

# module
import avwx
from avwx_api.handle.base import ReportHandler, ERRORS
from avwx_api.structs import Coord, DataStatus, ParseConfig


OPTIONS = ("summary", "speech", "translate")


class MetarHandler(ReportHandler):
    parser = avwx.Metar
    option_keys = OPTIONS
    history = True


class TafHandler(ReportHandler):
    parser = avwx.Taf
    option_keys = OPTIONS
    history = True


class PirepHandler(ReportHandler):
    parser: avwx.Pireps = avwx.Pireps
    report_type = "pirep"
    option_keys: tuple[str] = tuple()
    listed_data: bool = True

    async def fetch_report(
        self,
        loc: Union[avwx.Station, Coord],
        config: ParseConfig,
    ) -> DataStatus:
        """Returns weather data for the given report type, station, and options
        Also returns the appropriate HTTP response code

        Uses a cache to store recent report hashes which are (at most) two minutes old
        If nofail and a new report can't be fetched, the cache will be returned with a warning
        """
        station, code, cache = None, 200, None
        # If coordinates. We don't cache coordinates
        if isinstance(loc, tuple):
            parser = self.parser(lat=loc[0], lon=loc[1])
            data, code = await self._new_report(parser, cache=False)
        elif isinstance(loc, avwx.Station):
            station = loc
            if not station.sends_reports:
                return {"error": ERRORS[6].format(station.icao)}, 204
            data, cache, code = await self._station_cache_or_fetch(station)
        else:
            raise Exception(f"loc is not a valid value: {loc}")
        return await self._post_handle(data, code, cache, station, config)

    async def _parse_given(self, report: str, config: ParseConfig) -> DataStatus:
        """Attempts to parse a given report supplied by the user"""
        if len(report) < 3 or "{" in report:
            return ({"error": "Could not find station at beginning of report"}, 400)
        if report and report[:3] in ("ARP", "ARS"):
            return (
                {"error": "The report looks like an AIREP. Use /api/airep/parse"},
                400,
            )
        parser = self.parser("KJFK")  # We ignore the station
        parser.update(report)
        resp = asdict(parser.data[0])
        return resp, 200
