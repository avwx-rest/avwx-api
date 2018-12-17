"""
Michael duPont - michael@mdupont.com
avwx_api.views - Routes and views for the Quart application
"""

# pylint: disable=W0702

# library
from quart import jsonify
# module
from avwx_api import app

# Static Web Pages

@app.route('/')
@app.route('/home')
async def home():
    """
    Returns static home page
    """
    return await app.send_static_file('html/home.html')

# API Routing Errors

@app.route('/api')
async def no_report():
    """
    Returns no report msg
    """
    return jsonify({'Error': 'No report type given'}), 400

@app.route('/api/metar')
@app.route('/api/taf')
async def no_station():
    """
    Returns no station msg
    """
    return jsonify({'Error': 'No station given'}), 400
