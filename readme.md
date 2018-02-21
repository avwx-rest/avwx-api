# AVWX-API
AVWX service API as a Flask app on Azure  
Michael duPont - [mdupont.com](https://mdupont.com)

---

## About
![](https://avwx.rest/static/favicons/apple-icon-76x76.png)  
The AVWX REST API is a web service wrapper around an aviation weather function library I started as a [Raspberry Pi project](https://github.com/flyinactor91/METAR-RasPi) while finishing my private pilot certification. The standalone [library can be found here](https://github.com/flyinactor91/AVWX-Engine).

The API is a Python3 Flask application in a Docker container. It sources METAR and TAF reports from NOAA ADDS (the backend of [aviationweather.gov](http://aviationweather.gov)) but provides a more accurate parse especially for international reporting stations. The API accepts a station's ICAO identifier (ex. KJFK, EGLL) or coordinate pair (lat, lon), in which case it uses [GeoNames](http://www.geonames.org/) to return the nearest station. Reports are fully parsed with all possible request combinations and saved in a document cache (also on Azure) for up to two minutes.

Additional info can be found on the [service's about page](http://avwx.rest/about).

## Docker

The application can run in a Docker container with two services. The `docker-compose.yml` creates:

- `avwx-api`: A Flask application that runs the API
- `avwx-mongo`: A mongoDB container used for the cache

Both services will be part of a same [Docker network](https://docs.docker.com/network/network-tutorial-standalone/#use-user-defined-bridge-networks) `avwxapi_default`

### Dockerfile

Copy the example `Dockerfile.example` to `Docker` and replace your own API keys

```bash
cp Dockerfile.example Dockerfile
```


### Build & run

```bash
docker-compose build

# Run detached or attached by omitting the -d
docker-compose up -d
```

The service should be running on port `80`

```
curl http://0.0.0.0:80/api/metar/KSBP | jq
``` 

### Stopping 

```bash
docker-compose stop
```



## License

Copyright © 2017 Michael duPont  
[MIT License](https://github.com/flyinactor91/AVWX-API/blob/master/LICENSE)