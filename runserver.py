"""
This script runs the AVWX application using a development server.
"""

from avwx_api import app

app.run(port=8000, debug=True)
