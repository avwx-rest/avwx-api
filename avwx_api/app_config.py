"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

# stdlib
from os import environ

# library
from quart import got_request_exception
import rollbar

from rollbar.contrib.quart import report_exception

# module
from avwx_api_core.app import create_app
from avwx_api_core.cache import CacheManager
from avwx_api_core.token import TokenManager
from avwx_api.station_counter import StationCounter

app = create_app(__name__, environ.get("PSQL_URI"), environ.get("MONGO_URI"))


@app.before_serving
def init_helpers():
    """
    Init API helpers
    """
    app.cache = CacheManager(app)
    app.token = TokenManager(app)
    app.station = StationCounter(app)


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
