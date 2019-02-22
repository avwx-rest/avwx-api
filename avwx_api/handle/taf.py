"""
Michael duPont - michael@mdupont.com
avwx_api.handle.metar - Handle TAF requests
"""

from avwx_api.handle.metar import _handle_report, _parse_given

async def handle_report(loc: [str], opts: [str], nofail: bool = False) -> (dict, int):
    return await _handle_report('taf', loc, opts, nofail)

def parse_given(report: str, opts: [str]) -> (dict, int):
    return _parse_given('taf', report, opts)
