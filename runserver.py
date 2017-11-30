"""
This script runs the AVWX application using a development server.
"""

from avwx_api import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
