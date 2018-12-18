"""
Michael duPont - michael@mdupont.com
avwx_api.assistants - Endpoints and intents for voice assistants
"""

# library
import quart.flask_patch
import flask_assistant as assist
# import flask_ask as ask
# module
from avwx_api import app
from avwx_api.handling import handle_report

# Google Assistant intents

google = assist.Assistant(app, route='/google')

STATION_MAP = {
    'airport': 'sys.airport'
}

async def make_response(airport: dict, rtype: str) -> [str]:
    """
    Make the speech and text response for an airport and report type
    """
    wxret, status_code = await handle_report(rtype, [airport['ICAO']], ['summary', 'speech'])
    if status_code != 200:
        return assist.tell('There was a problem generating the response from the website')
    speech = 'Conditions at ' + airport['name'] + '. ' + wxret['speech']
    text = wxret['raw'] + ' —— ' + wxret['summary']
    return speech, text

@google.action('ask-metar', mapping=STATION_MAP)
async def metar_google(airport):
    """
    Return a spoken and display METAR response
    """
    speech, text = await make_response('metar', airport)
    return assist.tell(speech, display_text=text)

@google.action('ask-taf', mapping=STATION_MAP)
async def taf_google(airport):
    """
    Return a spoken and display TAF response
    """
    speech, text = await make_response('taf', airport)
    return assist.tell(speech, display_text=text)

# Amazon Alexa intents

# alexa = ask.Ask(app, '/alexa')

# import logging
# logging.getLogger("flask_ask").setLevel(logging.DEBUG)

# @alexa.launch
# def alexa_welcome():
#     return ask.question('Welcome to the aviation weather skill. How can I help you?')

# @alexa.intent('ask_metar', convert={'airport': str})
# def metar_alexa(airport):
#     """
#     """
#     print(airport)
#     wxret, status_code = handle_report('metar', [airport], ['summary', 'speech'])[0]
#     if status_code != 200:
#         return ask.statement('There was a problem generating the response from the website')
#     speech = wxret['Speech'].replace('kt.', ' knots.')
#     speech = 'Conditions at ' + airport + '. ' + speech
#     return ask.statement(speech).simple_card('METAR', wxret['Summary'])
