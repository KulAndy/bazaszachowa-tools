import json
import logging
import re
from datetime import date, datetime
from urllib.parse import quote_plus

import requests
import time
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from pymongo import MongoClient

from .. import settings

MONGO_URI = (
    f"mongodb://{quote_plus(settings.SETTINGS['mongo']['user'])}:"
    f"{quote_plus(settings.SETTINGS['mongo']['password'])}@"
    f"{settings.SETTINGS['mongo']['host']}:27017/{settings.SETTINGS['mongo']['database']}"
)
MONGO_COLLECTION = "fide_tournaments"
client = MongoClient(MONGO_URI)
db = client[settings.SETTINGS['mongo']['database']]
coll = db[MONGO_COLLECTION]

today = date.today().replace(day=1)
two_months_ago = today - relativedelta(months=2)

EVENT_RE = re.compile(r"/report\.phtml\?event=(\d+)")

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "pl-PL,pl;q=0.5",
    "X-Requested-With": "XMLHttpRequest",
})


def get_tournaments_in_base(country: str) -> list[int]:
    docs = coll.find({"country": country}, {"_id": 1})
    return [doc["_id"] for doc in docs]


def get_federations() -> set[str]:
    url = "https://ratings.fide.com/rated_tournaments.phtml"
    res = session.get(url)
    html = res.text

    soup = BeautifulSoup(html, "html.parser")
    select = soup.select_one("#select_country")

    if not select:
        raise RuntimeError("select#select_country not found")

    values = set([
        opt.get("value").strip()
        for opt in select.select("option")
        if opt.get("value", "").strip()
    ])
    values.remove("all")
    return values


def get_periods(country: str) -> list[str]:
    url = f"https://ratings.fide.com/a_tournaments_panel.php?country={country}&periods_tab=1"
    res = session.get(url)
    data = res.json() or []
    periods = [
        x["frl_publish"]
        for x in data
    ]
    return periods


def scrap_tournament(event_id: int | str) -> None:
    url = f"https://ratings.fide.com/report.phtml?event={event_id}"
    res = session.get(url)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.select_one("table.table2")

    if not table:
        raise RuntimeError("table.table2 not found")

    players = []
    for row in table.select("tr")[1:]:
        cells = row.select("td")
        if not cells or len(cells) < 9:
            continue
        player_id, name, fed, title, *_ = [c.get_text(strip=True) for c in cells]
        if player_id:
            players.append(int(player_id))

    coll.update_one(
        {"_id": int(event_id)},
        {"$set": {"players": players}},
        upsert=True
    )


def scrap_country_period(federation: str, period: str) -> None:
    period_date = date.fromisoformat(period)

    if period_date < two_months_ago:
        return
    IMPORTED_TOURNAMENTS = get_tournaments_in_base(federation)
    logging.info(f"{federation} {period}")
    url = f"https://ratings.fide.com/a_tournaments.php?country={federation}&period={period}&_={(time.time() * 100) // 1}"
    logging.debug(url)
    res = session.get(url)
    res.raise_for_status()
    data = res.content.decode("utf-8-sig")
    if not data:
        return
    data = json.loads(data)
    for row in data["data"]:
        logging.debug(row)
        logging.debug(len(row))
        event_id, href, site, system, start, *rest = row
        event_id = int(event_id)
        logging.debug(href)
        event = BeautifulSoup(href, "html.parser").get_text(strip=True)
        start_date = None
        for template in ["%d.%m.%Y", "%Y.%m.%d", "%Y-%m-%d"]:
            try:
                start_date = datetime.strptime(start, template)
                break
            except ValueError:
                pass

        logging.info("|".join([str(event_id), event, start_date.strftime("%Y-%m-%d")]))
        if start_date and event_id not in IMPORTED_TOURNAMENTS:
            coll.update_one(
                {"_id": int(event_id)},
                {"$set": {"country": federation, "name": event, "start": start_date}},
                upsert=True
            )
            time.sleep(0.1)


def main() -> None:
    session.get("https://ratings.fide.com/rated_tournaments.phtml")
    federations = get_federations()
    for federation in federations:
        logging.info(federation)
        periods = get_periods(federation)
        for period in periods:
            try:
                scrap_country_period(federation, period)
            except Exception as e:
                print(f"Error scrapping {federation}, {period}: {e}")
    coll.delete_many({"players": {"$exists": True, "$size": 0}})


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    main()
