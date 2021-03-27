"""
Michael duPont - michael@mdupont.com
avwx_api.structs - Parameter dataclasses
"""

# pylint: disable=missing-class-docstring,invalid-name

# stdlib
from dataclasses import dataclass
from typing import Union

# module
import avwx


Coord = tuple[float, float]
DataStatus = tuple[dict, int]


@dataclass
class Params:
    format: str


@dataclass
class Report(Params):
    options: list[str]
    report_type: str


@dataclass
class CachedReport(Report):
    onfail: str


@dataclass
class ReportStation(CachedReport):
    station: avwx.Station


@dataclass
class ReportStations(CachedReport):
    stations: list[avwx.Station]


@dataclass
class ReportLocation(CachedReport):
    location: Union[avwx.Station, Coord]


@dataclass
class ReportGiven(Report):
    report: str


@dataclass
class Station(Params):
    station: avwx.Station


@dataclass
class Stations(Params):
    stations: list[Station]


@dataclass
class StationSearch(Params):
    n: int
    airport: bool
    reporting: bool


@dataclass
class CoordSearch(StationSearch):
    coord: Coord
    maxdist: float


@dataclass
class TextSearch(StationSearch):
    text: str


@dataclass
class ReportCoordSearch(CachedReport, CoordSearch):
    pass


@dataclass
class ReportTextSearch(CachedReport, TextSearch):
    pass


@dataclass
class FlightRoute(Report):
    route: list[Coord]
    distance: float
