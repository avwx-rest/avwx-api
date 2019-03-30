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
from avwx_api.handle import update_parser, station_info, _HANDLE_MAP, ERRORS


async def new_report(rtype: str, params: dict) -> (dict, int):
    """
    Fetch and parse report data for given params
    """
    parser = _HANDLE_MAP[rtype](**params)
    error, code = await update_parser(parser, params)
    if error:
        return error, code
    data = {"data": [asdict(r) for r in parser.data], "units": asdict(parser.units)}
    if "station" in params:
        await cache.update(rtype, params["station"], data)
    return data, 200


async def _handle_report(
    rtype: str, loc: [str], opts: [str], nofail: bool = False
) -> (dict, int):
    """
    Returns weather data for the given report type, station, and options
    Also returns the appropriate HTTP response code

    Uses a cache to store recent report hashes which are (at most) two minutes old
    If nofail and a new report can't be fetched, the cache will be returned with a warning
    """
    resp = {"meta": {"timestamp": datetime.utcnow()}}
    station, data, code = None, None, 200
    # If station was given
    if len(loc) == 1:
        station = loc[0].upper()
        params = {"station": station}
        # Fetch an existing and up-to-date cache
        data, code = await cache.get(rtype, station), 200
    else:
        params = dict(zip(("lat", "lon"), loc))
    # If no cache, fetch a new report
    if not data:
        data, code = await new_report(rtype, params)
    if "timestamp" in data:
        resp["meta"]["cache-timestamp"] = data["timestamp"]
    # Handle errors according to nofail arguement
    if code != 200 and nofail:
        cache_data = await cache.get(rtype, station)
        if cache_data is None:
            resp["error"] = "No report or cache was found for the requested station"
            return resp, 400
        data = cache_data
        resp["meta"].update(
            {
                "cache-timestamp": data["timestamp"],
                "warning": "A no-fail condition was requested. This data might be out of date",
            }
        )
    resp.update(data)
    # Add station info if requested
    if station and "info" in opts:
        resp["info"] = station_info(station)
    # Update the cache with the new report data
    return resp, code


def _parse_given(rtype: str, report: str, opts: [str]) -> (dict, int):
    """
    Attepts to parse a given report supplied by the user
    """
    try:
        ureport = _HANDLE_MAP[rtype]("KJFK")  # We ignore the station
        ureport.update(report)
        resp = asdict(ureport.data[0])
        resp["meta"] = {"timestamp": datetime.utcnow()}
        return resp, 200
    except:
        # rollbar.report_exc_info()
        return {"error": ERRORS[1].format(rtype), "timestamp": datetime.utcnow()}, 500


async def handle_report(loc: [str], opts: [str], nofail: bool = False) -> (dict, int):
    return await _handle_report("pirep", loc, opts, nofail)


def parse_given(report: str, opts: [str]) -> (dict, int):
    if len(report) < 3 or "{" in report:
        return (
            {
                "error": "Could not find station at beginning of report",
                "timestamp": datetime.utcnow(),
            },
            400,
        )
    elif report.startswith("ARP"):
        return (
            {
                "error": "The report looks like an AIREP. Use /api/airep/parse",
                "timestamp": datetime.utcnow(),
            },
            400,
        )
    return _parse_given("pirep", report, opts)
