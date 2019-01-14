"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

# stdlib
from os import environ, path
# library
from quart import got_request_exception
from quart_openapi import Pint
import rollbar
# from rollbar.contrib.quart import report_exception
from avwx_api.rollbar_handler import report_exception

app = Pint(__name__)

@app.before_first_request
def init_rollbar():
    """
    Initialize Rollbar exception logging
    """
    key = environ.get('LOG_KEY')
    if not (key and app.env == 'production'):
        return
    rollbar.init(
        key,
        root=path.dirname(path.realpath(__file__)),
        allow_logging_basic_config=False
    )
    got_request_exception.connect(report_exception, app, weak=False)

from avwx_api import api, views
