"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

# stdlib
import asyncio as aio
from datetime import date
from os import environ

# library
from motor.motor_asyncio import AsyncIOMotorClient
from quart import g, got_request_exception
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


def get_db():
    """
    Returns the MongoDB client
    """
    if not hasattr(g, "db"):
        mongo_uri = environ.get("MONGO_URI")
        g.db = AsyncIOMotorClient(mongo_uri).report_cache if mongo_uri else None
    return g.db


from avwx_api import api, views
