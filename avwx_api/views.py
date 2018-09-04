"""
Michael duPont - michael@mdupont.com
avwx_api.views - Routes and views for the flask application
"""

# pylint: disable=W0702

# library
from flask import jsonify
# module
from avwx_api import app

# Static Web Pages

@app.route('/')
@app.route('/home')
def home():
    """
    Returns static home page
    """
    return app.send_static_file('html/home.html')

@app.route('/about')
def about():
    """
    Returns static about page
    """
    return app.send_static_file('html/about.html')

@app.route('/contact')
def contact():
    """
    Returns static contact page
    """
    return app.send_static_file('html/contact.html')

@app.route('/documentation')
def documentation():
    """
    Returns static documentation page
    """
    return app.send_static_file('html/documentation.html')

@app.route('/updates')
def updates():
    """
    Returns static updates page
    """
    return app.send_static_file('html/updates.html')

# API Routing Errors

@app.route('/api')
def no_report():
    """
    Returns no report msg
    """
    return jsonify({'Error': 'No report type given'}), 400

@app.route('/api/metar')
@app.route('/api/taf')
def no_station():
    """
    Returns no station msg
    """
    return jsonify({'Error': 'No station given'}), 400
