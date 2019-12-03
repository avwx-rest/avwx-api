"""
Michael duPont - michael@mdupont.com
avwx_api.handle.metar - Handle METAR requests
"""

# pylint: disable=E1101,W0703

# stdlib
import asyncio as aio
from dataclasses import asdict
from datetime import datetime, timezone

# library
import rollbar

# module
import avwx
from avwx_api import app
from avwx_api.handle import update_parser, _HANDLE_MAP, ERRORS

OPTION_KEYS = ("summary", "speech", "translate")


async def new_report(report_type: str, station: avwx.Station) -> (dict, int):
    """
    Fetch and parse report data for a given station
    """
    try:
        parser = _HANDLE_MAP[report_type](station.icao)
    except avwx.exceptions.BadStation:
        return {"error": f"{station.icao} does not publish reports"}, 400
    error, code = await update_parser(parser, station)
    if error:
        return error, code
    # Retrieve report data
    data = {
        "data": asdict(parser.data),
        "translate": asdict(parser.translations),
        "summary": parser.summary,
        "speech": parser.speech,
    }
    data["data"]["units"] = asdict(parser.units)
    # Update the cache with the new report data
    await aio.gather(
        app.cache.update(report_type, station.icao, data),
        app.history.add(report_type, parser.data),
    )
    return data, 200


def format_report(
    report_type: str, data: {str: object}, options: [str]
) -> {str: object}:
    """
    Formats the report/cache data into the expected response format
    """
    ret = data["data"]
    for opt in OPTION_KEYS:
        if opt in options:
            if opt == "summary" and report_type == "taf":
                for i in range(len(ret["forecast"])):
                    ret["forecast"][i]["summary"] = data["summary"][i]
            else:
                ret[opt] = data.get(opt)
    return ret


async def _handle_report(
    report_type: str, station: avwx.Station, opts: [str], nofail: bool = False
) -> (dict, int):
    """
    Returns weather data for the given report type, station, and options
    Also returns the appropriate HTTP response code

    Uses a cache to store recent report hashes which are (at most) two minutes old
    If nofail and a new report can't be fetched, the cache will be returned with a warning
    """
    if not station.sends_reports:
        return {"error": f"{station.icao} does not publish reports"}, 400
    # Fetch an existing and up-to-date cache or make a new report
    cache_data, code = await app.cache.get(report_type, station.icao, force=True), 200
    if cache_data is None or app.cache.has_expired(
        cache_data.get("timestamp"), report_type
    ):
        data, code = await new_report(report_type, station)
    else:
        data = cache_data
    resp = {"meta": {"timestamp": datetime.now(tz=timezone.utc)}}
    if "timestamp" in data:
        resp["meta"]["cache-timestamp"] = data["timestamp"]
    # Handle errors according to nofail argument
    if code != 200:
        if nofail:
            if cache_data is None:
                resp["error"] = "No report or cache was found for the requested station"
                return resp, 204
            data, code = cache_data, 200
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
    resp.update(format_report(report_type, data, opts))
    # Add station info if requested
    if "info" in opts:
        resp["info"] = asdict(station)
    return resp, code


def _parse_given(report_type: str, report: str, opts: [str]) -> (dict, int):
    """
    Attempts to parse a given report supplied by the user
    """
    if len(report) < 4 or "{" in report or "[" in report:
        return ({"error": "Could not find station at beginning of report"}, 400)
    try:
        station = avwx.Station.from_icao(report[:4])
    except avwx.exceptions.BadStation as exc:
        return {"error": str(exc)}, 400
    try:
        handler = _HANDLE_MAP[report_type].from_report(report)
        resp = asdict(handler.data)
        resp["meta"] = {"timestamp": datetime.now(tz=timezone.utc)}
        if "translate" in opts:
            resp["translations"] = asdict(handler.translations)
        if "summary" in opts:
            if report_type == "taf":
                for i in range(len(handler.translations["forecast"])):
                    resp["forecast"][i]["summary"] = handler.summary[i]
            else:
                resp["summary"] = handler.summary
        if "speech" in opts:
            resp["speech"] = handler.speech
        # Add station info if requested
        if "info" in opts:
            resp["info"] = asdict(station)
        return resp, 200
    except avwx.exceptions.BadStation:
        return {"error": ERRORS[2].format(station)}, 400
    except Exception as exc:
        print("Unknown Parsing Error", exc)
        rollbar.report_exc_info(extra_data={"state": "given", "raw": report})
        return {"error": ERRORS[1].format(report_type)}, 500


async def handle_report(
    station: avwx.Station, opts: [str], nofail: bool = False
) -> (dict, int):
    return await _handle_report("metar", station, opts, nofail)


def parse_given(report: str, opts: [str]) -> (dict, int):
    return _parse_given("metar", report, opts)
