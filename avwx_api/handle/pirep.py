"""
Michael duPont - michael@mdupont.com
avwx_api.handle.pirep - Handle PIREP requests
"""

# stdlib
from dataclasses import asdict
from datetime import datetime

# library
import avwx
import rollbar

# module
from avwx_api import cache
from avwx_api.handle import update_parser, _HANDLE_MAP, ERRORS


async def new_report(parser: avwx.Report, err_param: "stringable") -> (dict, int):
    """
    Fetch and parse report data for given params
    """
    error, code = await update_parser(parser, err_param)
    if error:
        return error, code
    data = {"data": [asdict(r) for r in parser.data], "units": asdict(parser.units)}
    return data, 200


async def _handle_report(
    report_type: str, loc: "Station/(float,)", opts: [str], nofail: bool = False
) -> (dict, int):
    """
    Returns weather data for the given report type, station, and options
    Also returns the appropriate HTTP response code

    Uses a cache to store recent report hashes which are (at most) two minutes old
    If nofail and a new report can't be fetched, the cache will be returned with a warning
    """
    station, data, code, cache_data = None, None, 200, None
    # If station was given
    if isinstance(loc, avwx.Station):
        station = loc
        if not station.sends_reports:
            return {"error": f"{station.icao} does not publish reports"}, 200
        # Fetch an existing and up-to-date cache
        cache_data, code = await cache.get(report_type, station.icao), 200
        # If no cache, get new data
        if cache_data is None or cache.has_expired(
            cache_data.get("timestamp"), report_type
        ):
            data, code = await new_report(
                _HANDLE_MAP[report_type](station_ident=station.icao), station.icao
            )
            if code == 200:
                await cache.update(report_type, station.icao, data)
        else:
            data = cache_data
    # Else coordinates. We don't cache coordinates
    else:
        data, code = await new_report(
            _HANDLE_MAP[report_type](lat=loc[0], lon=loc[1]), loc
        )
    resp = {"meta": {"timestamp": datetime.utcnow()}}
    if "timestamp" in data:
        resp["meta"]["cache-timestamp"] = data["timestamp"]
    # Handle errors according to nofail argument
    if code != 200 and nofail:
        if cache_data is None:
            resp["error"] = "No report or cache was found for the requested location"
            return resp, 204
        data = cache_data
        resp["meta"].update(
            {
                "cache-timestamp": data["timestamp"],
                "warning": "Unable to fetch reports. This cached data might be out of date. To return an error instead, set ?onfail=error",
            }
        )
    resp.update(data)
    # Add station info if requested
    if station and "info" in opts:
        resp["info"] = asdict(station)
    return resp, code


def _parse_given(report_type: str, report: str, opts: [str]) -> (dict, int):
    """
    Attempts to parse a given report supplied by the user
    """
    try:
        handler = _HANDLE_MAP[report_type]("KJFK")  # We ignore the station
        handler.update(report)
        resp = asdict(handler.data[0])
        resp["meta"] = {"timestamp": datetime.utcnow()}
        return resp, 200
    except Exception as exc:
        print("Unknown Parsing Error", exc)
        rollbar.report_exc_info(extra_data={"state": "given", "raw": report})
        return {"error": ERRORS[1].format(report_type)}, 500


async def handle_report(
    station: avwx.Station, opts: [str], nofail: bool = False
) -> (dict, int):
    return await _handle_report("pirep", station, opts, nofail)


def parse_given(report: str, opts: [str]) -> (dict, int):
    if len(report) < 3 or "{" in report:
        return ({"error": "Could not find station at beginning of report"}, 400)
    if report and report[:3] in ("ARP", "ARS"):
        return ({"error": "The report looks like an AIREP. Use /api/airep/parse"}, 400)
    return _parse_given("pirep", report, opts)
