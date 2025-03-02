"""Parameter dataclasses."""

# pylint: disable=missing-class-docstring,invalid-name

from dataclasses import dataclass
from http import HTTPStatus

import avwx
from avwx.structs import Coord
from avwx_api_core.structs import Params
from avwx_api_core.token import Token

DataStatus = tuple[dict, HTTPStatus]


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
    location: avwx.Station | Coord


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
class StationList(Params):
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


@dataclass
class DistanceFrom:
    distance: float


@dataclass
class ReportRoute(Report, FlightRoute, DistanceFrom):
    pass


@dataclass
class StationRoute(Params, FlightRoute, DistanceFrom):
    pass


@dataclass
class AirSigRoute(Params, FlightRoute):
    pass


@dataclass
class AirSigContains(Params):
    location: avwx.Station | Coord


@dataclass
class NotamLocation(ReportLocation, DistanceFrom):
    pass


@dataclass
class NotamRoute(Params, DistanceFrom):
    route: list[str]


_NAMED_OPTIONS = ("translate", "summary", "speech")


@dataclass
class ParseConfig:  # pylint: disable=too-many-instance-attributes
    """Config flags for report parse handling"""

    translate: bool
    summary: bool
    speech: bool
    station: bool
    aviowiki_data: bool
    cache_on_fail: bool
    nearest_on_fail: bool
    distance: int | None

    @staticmethod
    def use_aviowiki_data(token: Token | None) -> bool:
        """Returns True if a token has the AvioWiki Data addon"""
        return token and "awdata" in token.addons

    @classmethod
    def from_params(cls, params: Params, token: Token | None) -> "ParseConfig":
        """Create config from route inputs"""
        keys = getattr(params, "options", [])
        options = {key: key in keys for key in _NAMED_OPTIONS}
        return cls(
            **options,
            station="info" in keys,
            aviowiki_data=cls.use_aviowiki_data(token),
            cache_on_fail=getattr(params, "onfail", None) == "cache",
            nearest_on_fail=getattr(params, "onfail", None) == "nearest",
            distance=getattr(params, "distance", None),
        )
