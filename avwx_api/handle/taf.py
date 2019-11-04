"""
Michael duPont - michael@mdupont.com
avwx_api.handle.taf - Handle TAF requests
"""

from avwx import Station
from avwx_api.handle.metar import _handle_report, _parse_given


async def handle_report(
    station: Station, opts: [str], nofail: bool = False
) -> (dict, int):
    return await _handle_report("taf", station, opts, nofail)


def parse_given(report: str, opts: [str]) -> (dict, int):
    return _parse_given("taf", report, opts)
