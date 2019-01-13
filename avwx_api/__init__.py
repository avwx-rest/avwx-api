"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

from quart_openapi import Pint

app = Pint(__name__)

from avwx_api import api, views
