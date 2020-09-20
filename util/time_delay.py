"""
Tests update delays from different NOAA sources and the API
"""

# stdlib
from contextlib import suppress
from datetime import datetime
from time import sleep

# library
import httpx
from avwx import Metar
from avwx.service.scrape import NOAA_ADDS, NOAA_FTP, NOAA_Scrape, Service


def from_service(service: Service, icao: str) -> str:
    """
    Returns the timestamp fetched from an AVWX Service object
    """
    metar = Metar(icao)
    metar.update(service("metar").fetch(icao))
    return metar.data.time.repr


def from_api(icao: str) -> str:
    """
    Returns the timestamp fetched from the API
    """
    # NOTE: Disable token auth with prod cache
    data = httpx.get("http://localhost:8000/api/metar/" + icao).json()
    return data["time"]["repr"]


def get_times(icao: str) -> dict:
    """
    Returns a dictionary of current report timestamps from different services
    """
    return {
        "api": from_api(icao),
        "adds": from_service(NOAA_ADDS, icao),
        "ftp": from_service(NOAA_FTP, icao),
        "scrape": from_service(NOAA_Scrape, icao),
    }


def main():
    """
    Prints when there is a timestamp discrepency
    """
    icao = "KJFK"
    counter = 0
    while True:
        times = get_times(icao)
        if len(set(times.values())) != 1:
            print(datetime.utcnow(), times)
            print()
            counter = 0
        else:
            counter += 1
            print(counter, end="\r")
        sleep(60)


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        main()
