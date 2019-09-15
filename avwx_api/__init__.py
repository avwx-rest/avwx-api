"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

# stdlib
from datetime import date
from os import environ

# library
from motor.motor_asyncio import AsyncIOMotorClient
from quart import got_request_exception
from quart.json import JSONEncoder
from quart_openapi import Pint
import rollbar

from rollbar.contrib.quart import report_exception

app = Pint(__name__)


class CustomJSONEncoder(JSONEncoder):
    # pylint: disable=method-hidden
    def default(self, obj):
        try:
            if isinstance(obj, date):
                return obj.isoformat() + "Z"
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


app.json_encoder = CustomJSONEncoder


@app.before_first_request
def init_rollbar():
    """
    Initialize Rollbar exception logging
    """
    key = environ.get("LOG_KEY")
    if not (key and app.env == "production"):
        return
    rollbar.init(key, root="avwx_api", allow_logging_basic_config=False)
    got_request_exception.connect(report_exception, app, weak=False)


mdb = None


@app.before_serving
def init_clients():
    mongo_uri = environ.get("MONGO_URI")
    if mongo_uri:
        global mdb
        mdb = AsyncIOMotorClient(mongo_uri)


from avwx_api import api, views


@app.after_request
def after_request(response):
    """
    Add missing CORS headers

    Fixes CORS bug where headers are not included in OPTIONS
    """
    for key, value in (
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Headers", api.HEADERS),
        ("Access-Control-Allow-Methods", list(response.allow)),
    ):
        if key not in response.headers:
            if isinstance(value, list):
                value = ",".join(value)
            response.headers.add(key, value)
    return response
