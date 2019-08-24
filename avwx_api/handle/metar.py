"""
Michael duPont - michael@mdupont.com
avwx_api.handle.metar - Handle METAR requests
"""

# pylint: disable=E1101,W0703

# stdlib
from dataclasses import asdict
from datetime import datetime

# library
import avwx
import rollbar

# module
from avwx_api import cache
from avwx_api.handle import update_parser, _HANDLE_MAP, ERRORS

OPTION_KEYS = ("summary", "speech", "translate")


async def new_report(rtype: str, station: avwx.Station) -> (dict, int):
    """
    Fetch and parse report data for a given station
    """
    try:
        parser = _HANDLE_MAP[rtype](station.icao)
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
    await cache.update(rtype, station.icao, data)
    return data, 200


def format_report(rtype: str, data: {str: object}, options: [str]) -> {str: object}:
    """
    Formats the report/cache data into the expected response format
    """
    ret = data["data"]
    for opt in OPTION_KEYS:
        if opt in options:
            if opt == "summary" and rtype == "taf":
                for i in range(len(ret["forecast"])):
                    ret["forecast"][i]["summary"] = data["summary"][i]
            else:
                ret[opt] = data.get(opt)
    return ret


async def _handle_report(
    rtype: str, station: avwx.Station, opts: [str], nofail: bool = False
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
    cache_data, code = await cache.get(rtype, station.icao, force=True), 200
    if cache_data is None or cache.has_expired(cache_data.get("timestamp"), rtype):
        data, code = await new_report(rtype, station)
    else:
        data = cache_data
    resp = {"meta": {"timestamp": datetime.utcnow()}}
    if "timestamp" in data:
        resp["meta"]["cache-timestamp"] = data["timestamp"]
    # Handle errors according to nofail arguement
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
    resp.update(format_report(rtype, data, opts))
    # Add station info if requested
    if "info" in opts:
        resp["info"] = asdict(station)
    return resp, code


def _parse_given(rtype: str, report: str, opts: [str]) -> (dict, int):
    """
    Attepts to parse a given report supplied by the user
    """
    if len(report) < 4 or "{" in report or "[" in report:
        return ({"error": "Could not find station at beginning of report"}, 400)
    try:
        station = avwx.Station.from_icao(report[:4])
    except avwx.exceptions.BadStation as exc:
        return {"error": str(exc)}, 400
    try:
        ureport = _HANDLE_MAP[rtype].from_report(report)
        resp = asdict(ureport.data)
        resp["meta"] = {"timestamp": datetime.utcnow()}
        if "translate" in opts:
            resp["translations"] = asdict(ureport.translations)
        if "summary" in opts:
            if rtype == "taf":
                for i in range(len(ureport.translations["forecast"])):
                    resp["forecast"][i]["summary"] = ureport.summary[i]
            else:
                resp["summary"] = ureport.summary
        if "speech" in opts:
            resp["speech"] = ureport.speech
        # Add station info if requested
        if "info" in opts:
            resp["info"] = asdict(station)
        return resp, 200
    except avwx.exceptions.BadStation:
        return {"error": ERRORS[2].format(station)}, 400
    except Exception as exc:
        print("Unknown Parsing Error", exc)
        rollbar.report_exc_info(extra_data={"state": "given", "raw": report})
        return {"error": ERRORS[1].format(rtype)}, 500


async def handle_report(
    station: avwx.Station, opts: [str], nofail: bool = False
) -> (dict, int):
    return await _handle_report("metar", station, opts, nofail)


def parse_given(report: str, opts: [str]) -> (dict, int):
    return _parse_given("metar", report, opts)
