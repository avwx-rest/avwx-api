#!/usr/bin/python

#python3 avwxhandler.py metar json KLEX info
#python3 avwxhandler.py taf xml 28.123 43.456

from .dicttoxml import dicttoxml as fxml
from datetime import datetime, timedelta
import sys , avwx , json , sqlite3
if sys.version_info[0] == 2: import urllib2
elif sys.version_info[0] == 3: from urllib.request import urlopen
else: print("Cannot load urllib in avwxHandler.py")

reportsDBPath = 'reports.sqlite'

#Init connection to the report memoization database
conn = sqlite3.connect(reportsDBPath)
curs = conn.cursor()

#Prints a formatted xml string of 'aDict' and exits the script
def output(aDict):
    if sys.argv[2] == 'xml': print(fxml(aDict , custom_root=sys.argv[1].upper()))
    elif sys.argv[2] == 'json': print(json.dumps(aDict , sort_keys=True))
    sys.exit()

#Checks whether a string is a valid float value
def isFloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

#Returns station from geonames for station nearest lat/lon
#Calls output for any errors
def getDataByCoords(lat , lon):
    try:
        url = 'http://api.geonames.org/findNearByWeatherJSON?lat='+lat+'&lng='+lon+'&username=flyinactor91'
        if sys.version_info[0] == 2:
            response = urllib2.urlopen(url)
            html = response.read()
        elif sys.version_info[0] == 3:
            response = urlopen(url)
            html = response.read().decode('utf-8')
        xml = json.loads(html)
        if 'weatherObservation' in xml: return xml['weatherObservation']
        elif 'status' in xml: output({'Error':'Coord Lookup Error: ' + str(xml['status']['message'])})
        else: output({'Error':'Coord Lookup Error: Unknown Error (1)'})
    except Exception as e:
        output({'Error':'Coord Lookup Error: Unknown Error (0) / ' + str(e)})

#Fetch the report from the database if less than a minute old or from API
def fetchReport(station, reportType):
    curs.execute('SELECT * FROM '+reportType+' WHERE station=?', (station,))
    row = curs.fetchone()
    if row and row[3]:
        now = datetime.utcnow()
        if row[3] > (now-timedelta(seconds=60)).isoformat().replace('T', ' '):
            return row[1]
    if reportType == 'metar': return avwx.getMETAR(station)
    elif reportType == 'taf': return avwx.getTAF(station)

#Handles creation of the initial parsed dictionary using either the avwx
#parser or loading in the previously parsed JSON string
#Reutrns the parsed dictionary while handling the memoization database
def handleParsing(station , report , reportType):
    #Check memoization db if we've already parsed the report for the given station
    curs.execute('SELECT * FROM '+reportType+' WHERE station=?' , (station,))
    row = curs.fetchone()
    retDict = {}
    #If our rawtext matches the db rawtext, parse the db JSON string
    if row and len(row) == 3 and row[1] == report: retDict = json.loads(row[2])
    #Else, let avwx parse the report and update/insert the new report strings into the db
    else:
        if reportType == 'metar': retDict = avwx.parseMETAR(report.strip(' '))
        elif reportType == 'taf': retDict = avwx.parseTAF(report.strip(' ') , '<br/>&nbsp;&nbsp;')
        if row: curs.execute('UPDATE '+reportType+' SET station=?,rawtext=?,jsondict=?,updated=? WHERE station=?' , (station,report,json.dumps(retDict),datetime.utcnow(),station,))
        else: curs.execute('INSERT INTO '+reportType+' VALUES (?,?,?,?)' , (station,report,json.dumps(retDict),datetime.utcnow(),))
        conn.commit()
    return retDict

########Primary handling########

station = ''
report = ''
#If called with station
if len(sys.argv) > 3 and len(sys.argv[3]) == 4 and sys.argv[3].isalnum():
    station = sys.argv[3].upper()
#If called with coords
elif len(sys.argv) > 4 and isFloat(sys.argv[3]) and isFloat(sys.argv[4]):
    geoData = getDataByCoords(sys.argv[3] , sys.argv[4])
    if sys.argv[1] == 'metar':
        station = geoData['ICAO']
        report = geoData['observation']
    elif sys.argv[1] == 'taf': station = geoData['ICAO']
#Else bad input values
else:
    output({'Error':"URL must contain either 'station' or both 'lat' and 'lon' with proper values"})

#Fetch report
if station and not report:
    report = fetchReport(station, sys.argv[1])

#If there has been an error so far
if isinstance(report, int) or not report:
    output({'Error':'Station Lookup Error: {} not found for {} ({})'.format(sys.argv[1].upper(), station, report)})
#Else continue
else:
    #If we are parsing a METAR report
    if sys.argv[1] == 'metar':
        retDict = handleParsing(station , report , 'metar')
        if 'translate' in sys.argv: retDict['Translations'] = avwx.translateMETAR(retDict)
        if 'summary' in sys.argv: retDict['Summary'] = avwx.createMETARSummary(avwx.translateMETAR(retDict))
    #If we are parsing a TAF report
    elif sys.argv[1] == 'taf':
        retDict = handleParsing(station , report , 'taf')
        if 'translate' in sys.argv: retDict['Translations'] = avwx.translateTAF(retDict)
        if 'summary' in sys.argv:
            trans = avwx.translateTAF(retDict)
            for i in range(len(trans['Forecast'])): retDict['Forecast'][i]['Summary'] = avwx.createTAFLineSummary(trans['Forecast'][i])
    if 'info' in sys.argv: retDict['Info'] = avwx.getInfoForStation(station)
    output(retDict)
