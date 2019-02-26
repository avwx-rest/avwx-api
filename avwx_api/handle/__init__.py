"""
Michael duPont - michael@mdupont.com
avwx_api.handling - Data handling between inputs, cache, and avwx
"""

# stdlib
import asyncio as aio
from dataclasses import asdict
# library
import avwx
import rollbar

ERRORS = [
    "Station Lookup Error: {} not found for {}. There might not be a current report in ADDS",
    "Report Parsing Error: Could not parse {} report. An error report has been sent to the admin",
    "Station Lookup Error: {} does not appear to be a valid station. Please contact the admin",
    "Report Lookup Error: No {} reports were found for {}. Either the station doesn't exist or there are no active reports"
]

_HANDLE_MAP = {
    'metar': avwx.Metar,
    'taf': avwx.Taf,
    'pirep': avwx.Pireps,
}

def station_info(station: str) -> dict:
    """
    Return station info as a dict if available
    """
    try:
        return asdict(avwx.Station.from_icao(station))
    except avwx.exceptions.BadStation:
        return {}

async def update_parser(parser: avwx.Report, err_station: 'stringable' = None) -> (dict, int):
    """
    Updates the data of a given parser and returns any errors

    Attempts to fetch five times before giving up
    """
    rtype = parser.__class__.__name__.upper()
    try:
        for _ in range(5):
            try:
                if not await parser.async_update():
                    ierr = 0 if isinstance(err_station, str) else 3
                    return {'error': ERRORS[ierr].format(rtype, err_station)}, 400
                break
            except aio.TimeoutError:
                pass
    except avwx.exceptions.SourceError as exc:
        print('Source Error:', exc)
        return {'error': str(exc)}, int(str(exc)[-3:])
    except avwx.exceptions.InvalidRequest as exc:
        print('Invalid Request:', exc)
        return {'error': ERRORS[0].format(rtype, params)}, 400
    except Exception as exc:
        print('Unknown Error', exc)
        rollbar.report_exc_info()
        return {'error': ERRORS[1].format(rtype)}, 500
    if not parser.data:
        return {'error': 'Unable to reach data source after 5 attempts'}, 502
    return None, None

from avwx_api.handle import metar, taf, pirep
