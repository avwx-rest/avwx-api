"""
Michael duPont - michael@mdupont.com
avwx_api.handling - Data handling between inputs, cache, and avwx
"""

# stdlib
import asyncio as aio
from dataclasses import asdict

# library
import avwx
import rollbar

ERRORS = [
    "Station Lookup Error: {} not found for {}. There might not be a current report in ADDS",
    "Report Parsing Error: Could not parse {} report. An error report has been sent to the admin",
    "Station Lookup Error: {} does not appear to be a valid station. Please contact the admin",
    "Report Lookup Error: No {} reports were found for {}. Either the station doesn't exist or there are no active reports",
    "Report Lookup Error: An unknown error occurred fetch the {} report. An error report has been sent to the admin",
    "Report Lookup Error: Unable to fetch report from {}. You might wish to use '?onfail=cache' to return the most recent report even if it's not up-to-date",
]

_HANDLE_MAP = {"metar": avwx.Metar, "taf": avwx.Taf, "pirep": avwx.Pireps}


async def update_parser(
    parser: avwx.Report, err_station: "stringable" = None
) -> (dict, int):
    """
    Updates the data of a given parser and returns any errors

    Attempts to fetch five times before giving up
    """
    report_type = parser.__class__.__name__.upper()
    state_info = {
        "state": "fetch",
        "type": report_type,
        "station": getattr(parser, "station", None),
        "source": parser.service,
    }
    # Update the parser's raw data
    try:
        for _ in range(3):
            try:
                if not await parser.async_update(timeout=2, disable_post=True):
                    err = 0 if isinstance(err_station, str) else 3
                    return {"error": ERRORS[err].format(report_type, err_station)}, 400
                break
            except TimeoutError:
                pass
        else:
            # msg = f"Unable to call {parser.service.__class__.__name__}"
            # rollbar.report_message(msg, extra_data=state_info)
            return {"error": ERRORS[5].format(parser.service.__class__.__name__)}, 502
    except aio.CancelledError:
        print("Cancelled Error")
        return {"error": "Server rebooting. Try again"}, 503
    except ConnectionError as exc:
        print("Connection Error:", exc)
        rollbar.report_exc_info(extra_data=state_info)
        return {"error": str(exc)}, 502
    except avwx.exceptions.SourceError as exc:
        print("Source Error:", exc)
        rollbar.report_exc_info(extra_data=state_info)
        return {"error": str(exc)}, int(str(exc)[-3:])
    except avwx.exceptions.InvalidRequest as exc:
        print("Invalid Request:", exc)
        return {"error": ERRORS[0].format(report_type, err_station)}, 400
    except Exception as exc:
        print("Unknown Fetching Error", exc)
        rollbar.report_exc_info(extra_data=state_info)
        return {"error": ERRORS[4].format(report_type)}, 500
    # Parse the fetched data
    try:
        parser._post_update()
    except avwx.exceptions.BadStation as exc:
        print("Unknown Station:", exc)
        return {"error": ERRORS[2].format(parser.station)}, 400
    except Exception as exc:
        print("Unknown Parsing Error", exc)
        state_info["state"] = "parse"
        state_info["raw"] = parser.raw
        rollbar.report_exc_info(extra_data=state_info)
        return {"error": ERRORS[1].format(report_type), "raw": parser.raw}, 500
    return None, None


from avwx_api.handle import metar, taf, pirep
