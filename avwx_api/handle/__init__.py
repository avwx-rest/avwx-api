"""
Michael duPont - michael@mdupont.com
avwx_api.handling - Data handling between inputs, cache, and avwx
"""

# stdlib
from dataclasses import asdict
# library
import avwx

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

from avwx_api.handle import metar, taf, pirep
