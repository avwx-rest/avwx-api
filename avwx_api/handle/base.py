"""
Data handling between inputs, cache, and avwx core
"""

# pylint: disable=broad-except

# stdlib
import asyncio as aio
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# library
import rollbar

# module
import avwx
from avwx_api import app

ERRORS = [
    "Station Lookup Error: {} not found for {}. There might not be a current report in ADDS",
    "Report Parsing Error: Could not parse {} report. An error report has been sent to the admin",
    "Station Lookup Error: {} does not appear to be a valid station. Please contact the admin",
    "Report Lookup Error: No {} reports were found for {}. Either the station doesn't exist or there are no active reports",
    "Report Lookup Error: An unknown error occurred fetch the {} report. An error report has been sent to the admin",
    "Report Lookup Error: Unable to fetch report from {}. You might wish to use '?onfail=cache' to return the most recent report even if it's not up-to-date",
    "Station Error: {} does not publish reports",
]


class ReportHandler:
    """
    Handles AVWX report parsers and data formatting
    """

    parser: avwx.base.AVWXBase

    report_type: str = None
    option_keys: List[str] = None

    # Report data is a list
    listed_data: bool = False
    cache: bool = True
    history: bool = False

    def __init__(self):
        if not self.report_type:
            self.report_type = self.parser.__name__.lower()
        if self.option_keys is None:
            self.option_keys = tuple()

    @staticmethod
    def _make_meta() -> dict:
        """
        Create base metadata dict
        """
        return {
            "timestamp": datetime.now(tz=timezone.utc),
            "stations_updated": avwx.station.__LAST_UPDATED__,
        }

    def _make_data(self, parser: avwx.base.AVWXBase) -> dict:
        """
        Create the cached data representation from an updated parser
        """
        data = {}
        if self.listed_data:
            data["data"] = [asdict(r) for r in parser.data]
            data["units"] = asdict(parser.units)
        else:
            data["data"] = asdict(parser.data)
            data["data"]["units"] = asdict(parser.units)
        if "translate" in self.option_keys:
            data["translate"] = asdict(parser.translations)
        if "summary" in self.option_keys:
            data["summary"] = parser.summary
        if "speech" in self.option_keys:
            data["speech"] = parser.speech
        return data

    # pylint: disable=too-many-return-statements
    async def _update_parser(
        self, parser: avwx.base.AVWXBase, err_station: Any = None
    ) -> Tuple[dict, int]:
        """
        Updates the data of a given parser and returns any errors

        Attempts to fetch five times before giving up
        """
        state_info = {
            "state": "fetch",
            "type": self.report_type,
            "station": getattr(parser, "station", None),
            "source": parser.service,
        }
        # Update the parser's raw data
        try:
            for _ in range(3):
                with suppress(TimeoutError, avwx.exceptions.SourceError):
                    if not await parser.async_update(timeout=2, disable_post=True):
                        err = 0 if isinstance(err_station, str) else 3
                        return (
                            {
                                "error": ERRORS[err].format(
                                    self.report_type, err_station
                                )
                            },
                            400,
                        )
                    break
            else:
                # msg = f"Unable to call {parser.service.__class__.__name__}"
                # rollbar.report_message(msg, extra_data=state_info)
                return (
                    {"error": ERRORS[5].format(parser.service.__class__.__name__)},
                    502,
                )
        except aio.CancelledError:
            print("Cancelled Error")
            return {"error": "Server rebooting. Try again"}, 503
        except ConnectionError as exc:
            print("Connection Error:", exc)
            # rollbar.report_exc_info(extra_data=state_info)
            return {"error": str(exc)}, 502
        # except avwx.exceptions.SourceError as exc:
        #     print("Source Error:", exc)
        #     rollbar.report_exc_info(extra_data=state_info)
        #     return {"error": str(exc)}, int(str(exc)[-3:])
        except avwx.exceptions.InvalidRequest as exc:
            print("Invalid Request:", exc)
            return {"error": ERRORS[0].format(self.report_type, err_station)}, 400
        except Exception as exc:
            print("Unknown Fetching Error", exc)
            rollbar.report_exc_info(extra_data=state_info)
            return {"error": ERRORS[4].format(self.report_type)}, 500
        # Parse the fetched data
        try:
            parser._post_update()  # pylint: disable=protected-access
        except avwx.exceptions.BadStation as exc:
            print("Unknown Station:", exc)
            return {"error": ERRORS[2].format(parser.station)}, 400
        except Exception as exc:
            print("Unknown Parsing Error", exc)
            state_info["state"] = "parse"
            state_info["raw"] = parser.raw
            rollbar.report_exc_info(extra_data=state_info)
            return {"error": ERRORS[1].format(self.report_type), "raw": parser.raw}, 500
        return None, None

    async def _new_report(
        self, parser: avwx.base.AVWXBase, cache: bool = None, history: bool = None
    ) -> Tuple[dict, int]:
        """
        Fetch and parse report data for a given station
        """
        # Conditional defaults
        cache = self.cache if cache is None else cache
        history = self.history if history is None else history
        # Fetch a new parsed report
        location_key = parser.icao or (parser.lat, parser.lon)
        error, code = await self._update_parser(parser, location_key)
        if error:
            return error, code
        # Retrieve report data
        data = self._make_data(parser)
        # Update the cache with the new report data
        coros = []
        if cache:
            coros.append(app.cache.update(self.report_type, location_key, data))
        if coros:
            await aio.gather(*coros)
        return data, 200

    async def _station_cache_or_fetch(
        self,
        station: avwx.Station,
        force_cache: bool = False,
        use_cache: bool = None,
        add_history: bool = None,
    ):
        """
        For a station, fetch data from the cache or return a new report
        """
        data, code = None, 200
        cache = await app.cache.get(self.report_type, station.icao, force=force_cache)
        if cache is None or app.cache.has_expired(
            cache.get("timestamp"), self.report_type
        ):
            data, code = await self._new_report(
                self.parser(station.icao), use_cache, add_history
            )
        else:
            data = cache
        return data, cache, code

    def _format_report(
        self, data: Dict[str, object], options: List[str]
    ) -> Dict[str, object]:
        """
        Formats the report/cache data into the expected response format
        """
        ret = data.get("data", data)
        if isinstance(ret, list):
            return {"data": [self._format_report(item, options) for item in ret]}
        for opt in self.option_keys:
            if opt in options:
                if opt == "summary" and self.report_type == "taf":
                    for i in range(len(ret["forecast"])):
                        ret["forecast"][i]["summary"] = data["summary"][i]
                else:
                    ret[opt] = data.get(opt)
        return ret

    async def fetch_report(
        self, station: avwx.Station, opts: List[str], nofail: bool = False
    ) -> Tuple[dict, int]:
        """
        Returns weather data for the given report type, station, and options
        Also returns the appropriate HTTP response code

        Uses a cache to store recent report hashes which are (at most) two minutes old
        If nofail and a new report can't be fetched, the cache will be returned with a warning
        """
        if not station.sends_reports:
            return {"error": ERRORS[6].format(station.icao)}, 204
        # Fetch an existing and up-to-date cache or make a new report
        try:
            data, cache, code = await self._station_cache_or_fetch(
                station, force_cache=True
            )
            return self._post_handle(data, code, cache, station, opts, nofail)
        except Exception as exc:
            print("Unknown Parsing Error", exc)
            rollbar.report_exc_info(extra_data={"state": "outer fetch"})
            return {"error": ERRORS[1].format(self.report_type)}, 500

    # pylint: disable=too-many-arguments
    def _post_handle(
        self,
        data: dict,
        code: int,
        cache: dict,
        station: avwx.Station,
        opts: List[str],
        nofail: bool,
    ) -> Tuple[dict, int]:
        """
        Performs post parser update operations
        """
        resp = {"meta": self._make_meta()}
        if "timestamp" in data:
            resp["meta"]["cache-timestamp"] = data["timestamp"]
        # Handle errors according to nofail argument
        if code != 200:
            if nofail:
                if cache is None:
                    resp[
                        "error"
                    ] = "No report or cache was found for the requested station"
                    return resp, 204
                data, code = cache, 200
                resp["meta"].update(
                    {
                        "cache-timestamp": data["timestamp"],
                        "warning": "Unable to fetch report. This cached data might be out of date. To return an error instead, set ?onfail=error",
                    }
                )
            else:
                resp.update(data)
                return resp, code
        # Format the return data
        resp.update(self._format_report(data, opts))
        # Add station info if requested
        if station and "info" in opts:
            resp["info"] = asdict(station)
        return resp, code

    def _parse_given(self, report: str, opts: List[str]) -> Tuple[dict, int]:
        """
        Attempts to parse a given report supplied by the user
        """
        if len(report) < 4 or "{" in report or "[" in report:
            return ({"error": "Could not find station at beginning of report"}, 400)
        try:
            station = avwx.Station.from_icao(report[:4])
        except avwx.exceptions.BadStation:
            return {"error": ERRORS[2].format(report[:4])}, 400
        report = report.replace("\\n", "\n")
        parser = self.parser.from_report(report)
        resp = asdict(parser.data)
        if "translate" in opts:
            resp["translations"] = asdict(parser.translations)
        if "summary" in opts:
            if self.report_type == "taf":
                for i in range(len(parser.translations["forecast"])):
                    resp["forecast"][i]["summary"] = parser.summary[i]
            else:
                resp["summary"] = parser.summary
        if "speech" in opts:
            resp["speech"] = parser.speech
        # Add station info if requested
        if "info" in opts:
            resp["info"] = asdict(station)
        return resp, 200

    def parse_given(self, report: str, opts: List[str]) -> Tuple[dict, int]:
        """
        Attempts to parse a given report supplied by the user
        """
        try:
            data, code = self._parse_given(report, opts)
            data["meta"] = self._make_meta()
        except Exception as exc:
            print("Unknown Parsing Error", exc)
            rollbar.report_exc_info(extra_data={"state": "given", "raw": report})
            data, code = {"error": ERRORS[1].format(self.report_type)}, 500
        return data, code
