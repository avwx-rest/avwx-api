"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter validators
"""

# pylint: disable=invalid-name


from contextlib import suppress
from typing import Callable

from avwx import Station
from avwx.structs import Coord
from avwx_api_core.validate import (
    HELP_TEXT,
    FlightRoute,
    Latitude,
    Longitude,
    SplitIn,
    required,
    station_for,
)
from voluptuous import (
    REMOVE_EXTRA,
    All,
    Boolean,
    Coerce,
    In,
    Invalid,
    Length,
    Range,
    Required,
    Schema,
)

REPORT_TYPES = (
    "metar",
    "taf",
    "pirep",
    "airsigmet",
    "notam",
    "mav",
    "mex",
    "nbh",
    "nbs",
    "nbe",
    "summary",
)
OPTIONS = ("info", "translate", "summary", "speech")
ONFAIL = ("error", "cache", "nearest")


HELP = HELP_TEXT | {
    "onfail": f"Desired behavior when report fetch fails {ONFAIL}",
    "options": f'Response content and parsing options. Ex: "info,summary" in {OPTIONS}',
    "report": "Raw report string to be parsed. Given in the POST body as plain text",
    "report_type": f"Weather report type {REPORT_TYPES}",
    "station": 'ICAO, IATA, GPS code, or coord pair. Ex: KJFK, LHR, or "12.34,-12.34"',
    "location": 'ICAO, IATA, GPS code, or coord pair. Ex: KJFK, LHR, or "12.34,-12.34"',
    "stations": 'ICAO, IATA, or GPS codes. Ex: "KMCO,LEX,KJFK"',
    "coord": 'Coordinate pair. Ex: "12.34,-12.34"',
    "n": "Number of stations to return",
    "airport": "Limit results to airports",
    "reporting": "Limit results to reporting stations",
    "maxdist": "Max coordinate distance",
    "text": "Station search string. Ex: orlando%20kmco",
    "route": "Flight route made of ICAO, navaid, IATA, GPS code, or coordinate pairs. Ex: KLEX;ATL;29.2,-81.1;KMCO",
    "distance": "Statute miles from the route center",
}


def SplitChar(char: str) -> Callable:
    """Returns a validator to split a string by a specific character"""

    def validator(value: str) -> str:
        return value.split(char) if value else []

    return validator


def Coordinate(coord: str) -> Coord:
    """Converts a coordinate string into float tuple"""
    try:
        split = coord.split(",")
        return Coord(lat=Latitude(split[0]), lon=Longitude(split[1]), repr=coord)
    except Exception as exc:
        raise Invalid(f"{coord} is not a valid coordinate pair") from exc


def Location(
    coerce_station: bool = True, airport: bool = False, reporting: bool = True
) -> Callable:
    """Converts a station ident or coordinate pair string into a Station"""

    def validator(loc: str) -> Station | Coord:
        value = loc
        loc = loc.upper().split(",")
        if len(loc) == 1:
            return station_for(loc[0])
        if len(loc) == 2:
            try:
                lat, lon = Latitude(loc[0]), Longitude(loc[1])
                if coerce_station:
                    return Station.nearest(
                        lat, lon, is_airport=airport, sends_reports=reporting
                    )[0]
                return Coord(lat=lat, lon=lon, repr=value)
            except Exception as exc:
                raise Invalid(f"{value} is not a valid coordinate pair") from exc
        else:
            raise Invalid(f"{value} is not a valid station/coordinate pair")

    return validator


def MultiStation(values: str) -> list[Station]:
    """Validates a comma-separated list of station idents"""
    values = values.upper().split(",")
    if not values:
        raise Invalid("Could not find any stations in the request")
    if len(values) > 10:
        raise Invalid("Multi requests are limited to 10 stations or less")
    stations = []
    for code in values:
        with suppress(Invalid):
            stations.append(station_for(code))
    return stations


_report_shared = {
    **required,
    Required("options", default=""): SplitIn(OPTIONS),
    Required("report_type"): In(REPORT_TYPES),
}
_uses_cache = {Required("onfail", default="cache"): In(ONFAIL)}
_station_search = {
    Required("airport", default=True): Boolean(None),
    Required("reporting", default=True): Boolean(None),
}
_station_list = {Required("reporting", default=True): Boolean(None)}

_report_parse = {Required("report"): str}

_single_station = {Required("station"): Location()}
_multi_station = {Required("stations"): MultiStation}
_location = {Required("location"): Location(coerce_station=False)}

_flight_path = {Required("route"): FlightRoute}
_text_path = {Required("route"): SplitChar(";")}

_distance_from = {
    Required("distance", default=10): All(Coerce(int), Range(min=1, max=125))
}
_distance_along = {
    Required("distance", default=5): All(Coerce(float), Range(min=0, max=100))
}

_search_counter = {Required("n", default=10): All(Coerce(int), Range(min=1, max=200))}
_search_base = required | _station_search | _search_counter
_coord_search = {
    Required("coord"): Coordinate,
    Required("maxdist", default=10): All(Coerce(float), Range(min=0, max=360)),
}
_text_search = {Required("text"): Length(min=3, max=200)}


def _schema(schema: dict) -> Schema:
    return Schema(schema, extra=REMOVE_EXTRA)


def _coord_search_validator(param_name: str, coerce_station: bool) -> Callable:
    """Returns a validator the pre-validates nearest station parameters"""

    # NOTE: API class is passing self param to this function
    def validator(_, params: dict) -> dict:
        schema = _report_shared | _uses_cache
        search_params = _schema(_station_search)(params)
        schema[Required(param_name)] = Location(coerce_station, **search_params)
        return _schema(schema)(params)

    return validator


report_station = _coord_search_validator("station", True)
report_location = _coord_search_validator("location", False)

report_given = _schema(_report_shared | _report_parse)
report_along = _schema(_report_shared | _flight_path | _distance_along)
report_stations = _schema(_report_shared | _uses_cache | _multi_station)

global_report = _schema(_report_shared | _uses_cache)

station = _schema(required | _single_station)
stations = _schema(required | _multi_station)
station_along = _schema(required | _flight_path | _distance_along)
station_list = _schema(required | _station_list)

airsig_along = _schema(required | _flight_path)
airsig_contains = _schema(required | _location)

notam_location = _schema(_report_shared | _uses_cache | _location | _distance_from)
notam_along = _schema(required | _text_path | _distance_along)

coord_search = _schema(_search_base | _coord_search)
text_search = _schema(_search_base | _text_search)
report_coord_search = _schema(
    _search_base | _report_shared | _uses_cache | _coord_search
)
report_text_search = _schema(_search_base | _report_shared | _uses_cache | _text_search)
