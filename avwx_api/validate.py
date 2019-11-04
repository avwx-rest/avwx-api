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
    Range,
    Required,
    Schema,
    REMOVE_EXTRA,
)

# module
from avwx import Station
from avwx.exceptions import BadStation


REPORT_TYPES = ("metar", "taf", "pirep")
OPTIONS = ("info", "translate", "summary", "speech")
FORMATS = ("json", "xml", "yaml")
ONFAIL = ("error", "cache")


HELP = {
    "format": "Accepted response formats (json, xml, yaml)",
    "onfail": "Desired behavior when report fetch fails (error, cache)",
    "options": 'Response content and parsing options. Ex: "info,summary"',
    "report": "Raw report string to be parsed. Given in the POST body as plain text",
    "report_type": "Weather report type (metar, taf, pirep)",
    "station": 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"',
    "location": 'ICAO station ID or coord pair. Ex: KJFK or "12.34,-12.34"',
    "stations": 'ICAO station IDs. Ex: "KMCO,KLEX,KJFK"',
    "coord": 'Coordinate pair. Ex: "12.34,-12.34"',
    "n": "Number of stations to return",
    "airport": "Limit results to airports",
    "reporting": "Limit results to reporting stations",
    "maxdist": "Max coordinate distance",
}


# Includes non-airport reporting stations
# ICAO_WHITELIST = []


Latitude = All(Coerce(float), Range(-90, 90))
Longitude = All(Coerce(float), Range(-180, 180))


def Coordinate(coord: str) -> (float, float):
    """
    Converts a coordinate string into float tuple
    """
    try:
        split_coord = coord.split(",")
        return Latitude(split_coord[0]), Longitude(split_coord[1])
    except:
        raise Invalid(f"{coord} is not a valid coordinate pair")


def Location(
    coerce_station: bool = True, airport: bool = False, reporting: bool = True
) -> Callable:
    """
    Converts a station ident or coordinate pair string into a Station
    """

    def validator(loc: str) -> Station:
        loc = loc.upper().split(",")
        if len(loc) == 1:
            icao = loc[0]
            try:
                return Station.from_icao(icao)
            except BadStation:
                # if icao in ICAO_WHITELIST:
                #     return Station(*([None] * 4), "DNE", icao, *([None] * 9))
                raise Invalid(f"{icao} is not a valid ICAO station ident")
        elif len(loc) == 2:
            try:
                lat, lon = Latitude(loc[0]), Longitude(loc[1])
                if coerce_station:
                    return Station.nearest(
                        lat, lon, is_airport=airport, sends_reports=reporting
                    )[0]
                return lat, lon
            except:
                raise Invalid(f"{loc} is not a valid coordinate pair")
        else:
            raise Invalid(f"{loc} is not a valid station/coordinate pair")

    return validator


def MultiStation(stations: str) -> [Station]:
    """
    Validates a comma-separated list of station idents
    """
    stations = stations.upper().split(",")
    if not stations:
        raise Invalid("Could not find any stations in the request")
    if len(stations) > 10:
        raise Invalid("Multi requests are limited to 10 stations or less")
    ret = []
    for stn in stations:
        try:
            ret.append(Station.from_icao(stn))
        except BadStation:
            raise Invalid(f"{stn} is not a valid ICAO station ident")
    return ret


def SplitIn(values: (str,)) -> Callable:
    """
    Returns a validator to check for given values in a comma-separated string
    """

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
    Required("options", default=""): SplitIn(OPTIONS),
    Required("report_type"): In(REPORT_TYPES),
}
_uses_cache = {Required("onfail", default="cache"): In(ONFAIL)}
_station_search = {
    Required("airport", default=True): Boolean(None),
    Required("reporting", default=True): Boolean(None),
}


def _coord_search_validator(param_name: str, coerce_station: bool) -> Callable:
    """
    Returns a validator the pre-validates nearest station parameters
    """

    # NOTE: API class is passing self param to this function
    def validator(_, params: dict) -> dict:
        search_params = Schema(_station_search, extra=REMOVE_EXTRA)(params)
        return Schema(
            {
                **_required,
                **_report_shared,
                **_uses_cache,
                Required(param_name): Location(coerce_station, **search_params),
            },
            extra=REMOVE_EXTRA,
        )(params)

    return validator


report_station = _coord_search_validator("station", True)
report_location = _coord_search_validator("location", False)


report_given = Schema(
    {**_required, **_report_shared, Required("report"): str}, extra=REMOVE_EXTRA
)

report_stations = Schema(
    {**_required, **_report_shared, **_uses_cache, Required("stations"): MultiStation},
    extra=REMOVE_EXTRA,
)

station = Schema({**_required, Required("station"): Location()}, extra=REMOVE_EXTRA)

coord_search = Schema(
    {
        **_required,
        **_station_search,
        Required("coord"): Coordinate,
        Required("n", default=10): All(Coerce(int), Range(min=1, max=200)),
        Required("maxdist", default=10): All(Coerce(float), Range(min=0, max=360)),
    },
    extra=REMOVE_EXTRA,
)
