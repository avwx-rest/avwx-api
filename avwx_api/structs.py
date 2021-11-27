"""
Michael duPont - michael@mdupont.com
avwx_api.structs - Parameter dataclasses
"""

# pylint: disable=missing-class-docstring,invalid-name

# stdlib
from dataclasses import dataclass
from typing import Optional, Union

# module
import avwx
from avwx_api_core.structs import Coord
from avwx_api_core.token import Token


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
    stations: list[avwx.Station]


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
class FlightRoute:
    route: list[Coord]
    distance: float


@dataclass
class ReportRoute(Report, FlightRoute):
    pass


@dataclass
class StationRoute(Params, FlightRoute):
    pass


_NAMED_OPTIONS = ("translate", "summary", "speech")


@dataclass
class ParseConfig:
    """Config flags for report parse handling"""

    translate: bool
    summary: bool
    speech: bool
    station: bool
    aviowiki_data: bool
    cache_on_fail: bool

    @staticmethod
    def use_aviowiki_data(token: Optional[Token]) -> bool:
        """Returns True if a token has the AvioWiki Data addon"""
        return token and "awdata" in token.addons

    @classmethod
    def from_params(cls, params: Report, token: Optional[Token]) -> "ParseConfig":
        """Create config from route inputs"""
        options = {key: key in params.options for key in _NAMED_OPTIONS}
        return cls(
            **options,
            station="info" in params.options,
            aviowiki_data=cls.use_aviowiki_data(token),
            cache_on_fail=getattr(params, "onfail", None) == "cache",
        )
