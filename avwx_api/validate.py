"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter validators
"""

# pylint: disable=C0103

# stdlib
from typing import Callable

# library
from voluptuous import (
    All,
    Boolean,
    Coerce,
    In,
    Invalid,
    Length,
    Range,
    Required,
    Schema,
    REMOVE_EXTRA,
)

# module
from avwx import Station
from avwx.exceptions import BadStation
from avwx_api_core.structs import Coord
from avwx_api_core.validate import FlightRoute, Latitude, Longitude


REPORT_TYPES = ("metar", "taf", "pirep", "mav", "mex", "nbh", "nbs", "nbe")
OPTIONS = ("info", "translate", "summary", "speech")
FORMATS = ("json", "xml", "yaml")
ONFAIL = ("error", "cache")


HELP = {
    "format": f"Accepted response formats {FORMATS}",
    "onfail": f"Desired behavior when report fetch fails {ONFAIL}",
    "options": f'Response content and parsing options. Ex: "info,summary" in {OPTIONS}',
    "report": "Raw report string to be parsed. Given in the POST body as plain text",
    "report_type": f"Weather report type {REPORT_TYPES}",
    "station": 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"',
    "location": 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"',
    "stations": 'ICAO station IDs. Ex: "KMCO,KLEX,KJFK"',
    "coord": 'Coordinate pair. Ex: "12.34,-12.34"',
    "n": "Number of stations to return",
    "airport": "Limit results to airports",
    "reporting": "Limit results to reporting stations",
    "maxdist": "Max coordinate distance",
    "text": "Station search string. Ex: orlando%20kmco",
    "route": "Flight route made of ICAO, navaid, or coordinate pairs. Ex: KLEX;ATL;29.2,-81.1;KMCO",
    "distance": "Statute miles from the route center",
}


# Includes non-airport reporting stations
# ICAO_WHITELIST = []


def _station_for(code: str) -> Station:
    if len(code) == 3:
        return Station.from_iata(code)
    return Station.from_icao(code)


def Coordinate(coord: str) -> Coord:
    """Converts a coordinate string into float tuple"""
    try:
        split_coord = coord.split(",")
        return Latitude(split_coord[0]), Longitude(split_coord[1])
    except Exception as exc:
        raise Invalid(f"{coord} is not a valid coordinate pair") from exc


def Location(
    coerce_station: bool = True, airport: bool = False, reporting: bool = True
) -> Callable:
    """Converts a station ident or coordinate pair string into a Station"""

    def validator(loc: str) -> Station:
        loc = loc.upper().split(",")
        if len(loc) == 1:
            code = loc[0]
            try:
                return _station_for(code)
            except BadStation as exc:
                # if icao in ICAO_WHITELIST:
                #     return Station(*([None] * 4), "DNE", icao, *([None] * 9))
                raise Invalid(f"{code} is not a valid ICAO or IATA code") from exc
        elif len(loc) == 2:
            try:
                lat, lon = Latitude(loc[0]), Longitude(loc[1])
                if coerce_station:
                    return Station.nearest(
                        lat, lon, is_airport=airport, sends_reports=reporting
                    )[0]
                return lat, lon
            except Exception as exc:
                raise Invalid(f"{loc} is not a valid coordinate pair") from exc
        else:
            raise Invalid(f"{loc} is not a valid station/coordinate pair")

    return validator


def MultiStation(values: str) -> list[Station]:
    """Validates a comma-separated list of station idents"""
    values = values.upper().split(",")
    if not values:
        raise Invalid("Could not find any stations in the request")
    if len(values) > 10:
        raise Invalid("Multi requests are limited to 10 stations or less")
    ret = []
    for code in values:
        try:
            ret.append(_station_for(code))
        except BadStation as exc:
            raise Invalid(f"{code} is not a valid ICAO of IATA code") from exc
    return ret


def SplitIn(values: tuple[str]) -> Callable:
    """Returns a validator to check for given values in a comma-separated string"""

    def validator(csv: str) -> str:
        if not csv:
            return []
        split = csv.split(",")
        for val in split:
            if val not in values:
                raise Invalid(f"'{val}' could not be found in {values}")
        return split

    return validator


_required = {Required("format", default="json"): In(FORMATS)}
_report_shared = {
    **_required,
    Required("options", default=""): SplitIn(OPTIONS),
    Required("report_type"): In(REPORT_TYPES),
}
_uses_cache = {Required("onfail", default="cache"): In(ONFAIL)}
_station_search = {
    Required("airport", default=True): Boolean(None),
    Required("reporting", default=True): Boolean(None),
}

_report_parse = {Required("report"): str}

_single_station = {Required("station"): Location()}
_multi_station = {Required("stations"): MultiStation}

_flight_path = {
    Required("distance"): All(Coerce(float), Range(min=0, max=100)),
    Required("route"): FlightRoute,
}

_search_counter = {Required("n", default=10): All(Coerce(int), Range(min=1, max=200))}
_search_base = _required | _station_search | _search_counter
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
report_along = _schema(_report_shared | _flight_path)
report_stations = _schema(_report_shared | _uses_cache | _multi_station)

station = _schema(_required | _single_station)
stations = _schema(_required | _multi_station)
station_along = _schema(_required | _flight_path)

coord_search = _schema(_search_base | _coord_search)
text_search = _schema(_search_base | _text_search)
report_coord_search = _schema(
    _search_base | _report_shared | _uses_cache | _coord_search
)
report_text_search = _schema(_search_base | _report_shared | _uses_cache | _text_search)
