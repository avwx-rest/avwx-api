"""
Michael duPont - michael@mdupont.com
avwx_api.__init__ - High-level Flask application
"""

from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
cors = CORS(app, resources={
    r'/api/*': {'origins': '*'}
})

import avwx_api.views
