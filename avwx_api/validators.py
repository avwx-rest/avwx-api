"""
Michael duPont - michael@mdupont.com
avwx_api.validators - Parameter validators
"""

# stdlib
from typing import Callable

# library
from avwx import Station
from avwx.exceptions import BadStation
from voluptuous import All, Coerce, In, Invalid, Range, Required, Schema, REMOVE_EXTRA


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
}


Latitude = All(Coerce(float), Range(-90, 90))
Longitude = All(Coerce(float), Range(-180, 180))


def Location(coerce_station: bool = True) -> Callable:
    """
    Converts a station ident or coordinate pair string into a Station
    """

    def validator(loc: str):
        loc = loc.upper().split(",")
        if len(loc) == 1:
            try:
                return Station.from_icao(loc[0])
            except BadStation:
                raise Invalid(f"{loc[0]} is not a valid ICAO station ident")
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
    for station in stations:
        try:
            ret.append(Station.from_icao(station))
        except BadStation:
            raise Invalid(f"{station} is not a valid ICAO station ident")
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


_shared = {
    Required("format", default="json"): All(str, In(FORMATS)),
    Required("options", default=""): All(str, SplitIn(OPTIONS)),
    Required("report_type"): All(str, In(REPORT_TYPES)),
}

_location = {**_shared, Required("onfail", default="error"): All(str, In(ONFAIL))}

station = Schema(
    {**_location, Required("station"): All(str, Location())}, extra=REMOVE_EXTRA
)

location = Schema(
    {**_location, Required("location"): All(str, Location(coerce_station=False))},
    extra=REMOVE_EXTRA,
)

report = Schema({**_shared, "report": str}, extra=REMOVE_EXTRA)

stations = Schema(
    {**_location, Required("stations"): All(str, MultiStation)}, extra=REMOVE_EXTRA
)
