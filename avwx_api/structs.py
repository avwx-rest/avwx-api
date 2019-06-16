"""
Michael duPont - michael@mdupont.com
avwx_api.structs - Paramter dataclasses
"""

from dataclasses import dataclass


@dataclass
class Params:
    format: str


@dataclass
class ReportParams(Params):
    options: [str]
    report_type: str


@dataclass
class ReportStationParams(ReportParams):
    onfail: str
    station: "avwx.Station"


@dataclass
class ReportStationsParams(ReportParams):
    onfail: str
    stations: ["avwx.Station"]


@dataclass
class ReportLocationParams(ReportParams):
    location: "avwx.Station/(float, float)"
    onfail: str


@dataclass
class ReportGivenParams(ReportParams):
    report: str


@dataclass
class StationParams(Params):
    station: "avwx.Station"


@dataclass
class CoordSearchParams:
    coord: (float, float)
    n: int
    reporting: bool
    maxdist: float
    format: str
