"""
Michael duPont - michael@mdupont.com
avwx_api.structs - Parameter dataclasses
"""

# pylint: disable=missing-class-docstring,invalid-name

# stdlib
from dataclasses import dataclass
from typing import List, Tuple, Union

# module
from avwx import Station


@dataclass
class Params:
    format: str


@dataclass
class ReportParams(Params):
    options: List[str]
    report_type: str


@dataclass
class ReportStationParams(ReportParams):
    onfail: str
    station: Station


@dataclass
class ReportStationsParams(ReportParams):
    onfail: str
    stations: List[Station]


@dataclass
class ReportLocationParams(ReportParams):
    location: Union[Station, Tuple[float, float]]
    onfail: str


@dataclass
class ReportGivenParams(ReportParams):
    report: str


@dataclass
class StationParams(Params):
    station: Station


@dataclass
class StationsParams(Params):
    stations: List[Station]


@dataclass
class StationSearch(Params):
    n: int
    airport: bool
    reporting: bool


@dataclass
class CoordSearchParams(StationSearch):
    coord: Tuple[float, float]
    maxdist: float


@dataclass
class TextSearchParams(StationSearch):
    text: str
