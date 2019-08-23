"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter validators
"""

# stdlib
from typing import Callable

# library
from avwx import Station
from avwx.exceptions import BadStation
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
ICAO_WHITELIST = ("EHFS", "EHSA")


Latitude = All(Coerce(float), Range(-90, 90))
Longitude = All(Coerce(float), Range(-180, 180))


def Coordinate(coord: str) -> (float, float):
    """
    Converts a coordinate string into float tuple
    """
    try:
        cstr = coord.split(",")
        return Latitude(cstr[0]), Longitude(cstr[1])
    except:
        raise Invalid(f"{coord} is not a valid coordinate pair")


def Location(coerce_station: bool = True) -> Callable:
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
                if icao in ICAO_WHITELIST:
                    return Station(*([None] * 4), "DNE", icao, *([None] * 9))
                raise Invalid(f"{icao} is not a valid ICAO station ident")
        elif len(loc) == 2:
            try:
                lat, lon = Latitude(loc[0]), Longitude(loc[1])
                if coerce_station:
                    return Station.nearest(lat, lon)[0]
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
_uses_cache = {Required("onfail", default="error"): In(ONFAIL)}

report_station = Schema(
    {**_required, **_report_shared, **_uses_cache, Required("station"): Location()},
    extra=REMOVE_EXTRA,
)

report_location = Schema(
    {
        **_required,
        **_report_shared,
        **_uses_cache,
        Required("location"): Location(coerce_station=False),
    },
    extra=REMOVE_EXTRA,
)

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
        Required("coord"): Coordinate,
        Required("n", default=10): All(Coerce(int), Range(min=1, max=200)),
        Required("airport", default=True): Boolean(None),
        Required("reporting", default=True): Boolean(None),
        Required("maxdist", default=10): All(Coerce(float), Range(min=0, max=360)),
    },
    extra=REMOVE_EXTRA,
)
