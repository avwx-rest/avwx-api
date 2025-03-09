"""API app configuration."""

from os import environ

import rollbar
from avwx import exceptions as avwx_exceptions
from avwx_api_core.app import CustomJSONProvider, add_cors
from avwx_api_core.cache import CacheManager
from avwx_api_core.token import TokenManager
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from quart import got_request_exception
from quart_openapi import Pint
from rollbar.contrib.quart import report_exception

from avwx_api.station_counter import StationCounter

load_dotenv()


CACHE_EXPIRES = {"metar": 1, "taf": 1, "awdata": 60 * 24}
MONGO_URI = environ.get("MONGO_URI")


Pint.json_provider_class = CustomJSONProvider
app = Pint(__name__)

app.after_request(add_cors)


def init_rollbar() -> None:
    """Initialize Rollbar exception logging"""
    key = environ.get("LOG_KEY")
    # if not (key and app.env == "production"):
    #     return
    rollbar.init(key, root="avwx_api", allow_logging_basic_config=False)
    got_request_exception.connect(report_exception, app, weak=False)

    def exception_intercept(exception: Exception, **extra: dict) -> None:
        rollbar.report_exc_info(exception, extra_data=extra)

    avwx_exceptions.exception_intercept = exception_intercept


async def init_cache_only_map() -> None:
    """Fetch cache-only station lists for the duration of the worker"""
    if app.mdb is None:
        return
    for table in ("awos",):
        codes = await app.mdb.cache[table].distinct("_id")
        app.cache_only.update({code: table for code in codes})


async def load_noaa_stations() -> None:
    """Load NOAA station codes from station cache.

    This is used to determine if a station should be checked with the default provider.
    """
    if app.mdb is None:
        return
    if data := await app.mdb.cache["noaa-stations"].find_one({"_id": "metar"}):
        app.noaa_stations.update(data["stations"])
    else:
        print("Failed to load noaa_stations")


@app.before_serving
async def init_helpers() -> None:
    """Init API helpers

    Need async to connect helpers to event loop
    """
    app.mdb = AsyncIOMotorClient(MONGO_URI) if MONGO_URI else None
    app.cache = CacheManager(app, expires=CACHE_EXPIRES)
    app.token = TokenManager(app)
    app.station = StationCounter(app)
    app.cache_only = {}
    app.noaa_stations = set()
    init_rollbar()
    await init_cache_only_map()
    await load_noaa_stations()
