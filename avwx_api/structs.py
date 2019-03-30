"""
Michael duPont - michael@mdupont.com
avwx_api.structs - Paramter dataclasses
"""

from dataclasses import dataclass


@dataclass
class Params(object):
    format: str
    options: [str]
    report_type: str


@dataclass
class FetchParams(Params):
    onfail: str
    station: str


@dataclass
class GivenParams(Params):
    report: str
