# AVWX-API
AVWX service API as a Flask app on Azure  
Michael duPont - [mdupont.com](https://mdupont.com)

---

## About
![](https://avwx.rest/static/favicons/apple-icon-76x76.png)  
The AVWX REST API is a web service wrapper around an aviation weather function library I started as a [Raspberry Pi project](https://github.com/flyinactor91/METAR-RasPi) while finishing my private pilot certification. The standalone [library can be found here](https://github.com/flyinactor91/AVWX-Engine).

The API is a Python3 Flask application hosted on Microsoft Azure as an API App as part of the App Service. It sources METAR and TAF reports from NOAA ADDS (the backend of [aviationweather.gov](http://aviationweather.gov)) but provides a more accurate parse especially for international reporting stations. The API accepts a station's ICAO identifier (ex. KJFK, EGLL) or coordinate pair (lat, lon), in which case it uses [GeoNames](http://www.geonames.org/) to return the nearest station. Reports are fully parsed with all possible request combinations and saved in a document cache (also on Azure) for up to two minutes.

This is the second generation of the API and the first one made fully open-source. The previous one was a combination of Python and PHP endpoints which was cobbled together and worked well enough to get the service started. The old version can still be seen in this application as the old endpoints are still available in the routing. This new version is 100% Python3, much faster, and more scalable (up and out). The old version became bogged down once it hit 8K requests an hour; the new version has been load-tested to support that many in 30 seconds before a single connection error (with 3 to 10 dynamically-scaling servers).

Additional info can be found on the [service's about page](http://avwx.rest/about).

## License

Copyright © 2016 Michael duPont  
[MIT License](https://github.com/flyinactor91/AVWX-API/blob/master/LICENSE)