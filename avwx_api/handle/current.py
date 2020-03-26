"""
Handle current report requests
"""

# stdlib
from dataclasses import asdict

# module
import avwx
from avwx_api.handle.base import ReportHandler, ERRORS


OPTIONS = ("summary", "speech", "translate")


class MetarHandler(ReportHandler):
    report_type = "metar"
    parser = avwx.Metar
    option_keys = OPTIONS
    history = True


class TafHandler(ReportHandler):
    report_type = "taf"
    parser = avwx.Taf
    option_keys = OPTIONS
    history = True


class PirepHandler(ReportHandler):

    report_type: str = "pirep"
    parser: avwx.Pireps = avwx.Pireps
    option_keys: [str] = tuple()
    listed_data: bool = True

    async def fetch_report(
        self, loc: "Station/(float,)", opts: [str], nofail: bool = False
    ) -> (dict, int):
        """
        Returns weather data for the given report type, station, and options
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
        return self._post_handle(data, code, cache, station, opts, nofail)

    def _parse_given(self, report: str, opts: [str]) -> (dict, int):
        """
        Attempts to parse a given report supplied by the user
        """
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
