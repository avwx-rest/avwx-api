"""
Expand station counts into date documents
"""

# stdlib
from datetime import datetime
from os import environ
from typing import Dict

# library
from pymongo import MongoClient, UpdateOne


def make_update(icao: str, date: datetime, reports: Dict[str, dict]) -> UpdateOne:
    """Returns an UpdateOne operation for counts on a day"""
    return UpdateOne(
        {"icao": icao, "date": date},
        {"$inc": reports},
        upsert=True,
    )


def main() -> int:
    """Expand station counts into date documents"""
    coll = MongoClient(environ["MONGO_URI"]).counter.station
    while item := coll.find_one({"date": {"$exists": False}}):
        icao = item.pop("_id")
        print(icao)
        counts = {}
        date = None
        for report, dates in item.items():
            for date, count in dates.items():
                date = datetime.strptime(date, r"%Y-%m-%d")
                try:
                    counts[date][report] = count
                except KeyError:
                    counts[date] = {report: count}
        updates = [make_update(icao, date, count) for date, count in counts.items()]
        print(icao, len(updates))
        coll.bulk_write(updates, ordered=False)
        print("Deleting")
        coll.delete_one({"_id": icao})
    return 0


if __name__ == "__main__":
    main()
