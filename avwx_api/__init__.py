"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Quart application
"""

from quart_openapi import Pint

app = Pint(__name__)

import avwx_api.views
import avwx_api.api
# import avwx_api.assistants
