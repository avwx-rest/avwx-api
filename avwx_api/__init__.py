from flask import Flask

app = Flask(__name__)

import avwx_api.views
