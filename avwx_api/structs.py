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
class StationParams(Params):
    onfail: str
    station: "avwx.Station"


@dataclass
class LocationParams(Params):
    location: "avwx.Station/(float, float)"
    onfail: str


@dataclass
class GivenParams(Params):
    report: str
