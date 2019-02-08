"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

# stdlib
from datetime import date
from os import environ, path
# library
from quart import got_request_exception
from quart.json import JSONEncoder
from quart_openapi import Pint
import rollbar
# from rollbar.contrib.quart import report_exception
from avwx_api.rollbar_handler import report_exception

app = Pint(__name__)

class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, date):
                return obj.isoformat()
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
