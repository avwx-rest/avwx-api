# AVWX-API

![](https://avwx.rest/static/favicons/apple-icon-76x76.png)

[![Requirements Status](https://requires.io/github/flyinactor91/AVWX-Account/requirements.svg?branch=master)](https://requires.io/github/flyinactor91/AVWX-API/requirements/?branch=master)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## About

The AVWX REST API is built as a Python Quart app which is a Flask-compatible async web backend. It sources METAR and TAF reports from NOAA ADDS and other localized weather sources (where available) via the [AVWX-Engine library](https://github.com/flyinactor91/AVWX-Engine) which I also maintain.

The core benefit of AVWX over other sources is its parsing engine. It provides a more accurate interpretation of the raw report string than aging government sources and includes value-added features like calculating flight-rules, translating report elements into English, and providing text-to-speech representations of the report and its elements.

For more information, go to the hosted version at [avwx.rest](https://avwx.rest).

## Quickstart

The easiest way to get the app running is to create and run it in Docker. First, copy to example Dockerfile.

```bash
cp Dockerfile.example Dockerfile
```

Now we need to comment out three ENV vars in the Dockerfile. These are grouped together:

```
ENV MONGO_URI='...'
ENV PSQL_URI='...'
ENV GN_USER='...'
```

A quick explanation of what these do:

- `MONGO_URI`: This connects the app to the request caching database. Commenting out disables caching
- `PSQL_URI`: This connects the app to the account database for things like token authentication. Commenting out opens all endpoints
- `GN_USER`: This is the GeoNames user name for coordinate lookup calls. Commenting out causes coord requests to fail. You can supply your own for testing

Now you should be able to build and run the Docker container:

```bash
docker build -t avwx_api .
docker run -p 8000:8000 avwx_api
```

It should now be available at [http://localhost:8000](http://localhost:8000)

## Setup

First we should install the app requirements and copy the env file. I recommend always installing into a virtual environment. Dotenv is not in the requirements file because it is only used in development.

```bash
pip install -r requirements.txt
pip install python-dotenv
cp .env.sample .env
```

For an explaination of the variables in `.env`, see the quickstart. Feel free to comment or replace these as you see fit.

Before we can run the app, we need to tell Quart where the app is.

```bash
export QUART_APP=avwx_api:app
export QUART_ENV=development
```

## Running

Once the app is configured, use the Quart CLI to run it. It will be in development/debug mode.

```bash
quart run -p 8000
```

It should now be available at [http://localhost:8000](http://localhost:8000)
