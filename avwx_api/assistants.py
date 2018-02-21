"""
Michael duPont - michael@mdupont.com
avwx_api.assistants - Endpoints and intents for voice assistants
"""

# library
import flask_assistant as assist
# module
from avwx_api import app
from avwx_api.handling import handle_report

# Google Assistant intents

# To update the Google Assistant engine, run
# > schema avwx_api/assistants.py
# from the project root.

# Make sure to comment out calls to avwx_api
# Intent utterances are put in templates/user_says.yaml

# from flask import Flask
# app = Flask(__name__)
google = assist.Assistant(app, route='/google')

STATION_MAP = {
    'airport': 'sys.airport'
}

@google.action('ask-metar', mapping=STATION_MAP)
def metar_google(airport):
    """
    Return a spoken and display METAR response
    """
    wxret = handle_report('metar', [airport['ICAO']], ['summary', 'speech'])
    speech = 'Conditions at ' + airport['name'] + '. ' + wxret['Speech']
    text = wxret['Raw-Report'] + ' —— ' + wxret['Summary']
    return assist.tell(speech, display_text=text)

@google.action('ask-taf', mapping=STATION_MAP)
def taf_google(airport):
    """
    Return a spoken and display TAF response
    
    Not yet implemented by AVWX
    """
    return assist.tell('Sorry. Spoken TAF reports are not yet supported by AVWX')
