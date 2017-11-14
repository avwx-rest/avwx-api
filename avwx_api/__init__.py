"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Flask application
"""

from flask import Flask

app = Flask(__name__)

import avwx_api.views
