import re
import time
from datetime import date, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from ..settings import SETTINGS


MONGO_URI = (
    f"mongodb://{quote_plus(SETTINGS['mongo']['user'])}:"
    f"{quote_plus(SETTINGS['mongo']['password'])}@"
    f"{SETTINGS['mongo']['host']}:27017/{SETTINGS['mongo']['database']}"
)
MONGO_COLLECTION = "fide_tournaments"

client = MongoClient(MONGO_URI)
db = client[SETTINGS['mongo']['database']]
coll = db[MONGO_COLLECTION]
today = date.today().replace(day=1)
two_months_ago = today - relativedelta(months=2)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "http://www.cr-pzszach.pl/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
EVENT_RE = re.compile(r"/report\.phtml\?event=(\d+)")
TIMEOUT = 15


def get_federations():
    url = "https://ratings.fide.com/rated_tournaments.phtml"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    select = soup.select_one("#select_country")

    if not select:
        raise RuntimeError("select#select_country not found")

    return [
        opt.get("value").strip()
        for opt in select.select("option")
        if opt.get("value", "").strip()
    ]


def get_tournaments_in_base(country):
    docs = coll.find({"country": country}, {"_id": 1})
    return [doc["_id"] for doc in docs]


def scrap_tournament(event_id):
    url = f"https://ratings.fide.com/report.phtml?event={event_id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
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


def scrap_country_period(country, period):
    IMPORTED_TOURNAMENTS = get_tournaments_in_base(country)

    url = f"https://ratings.fide.com/rated_tournaments.phtml?country={country}&period={period}"
    print(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#main_table")
    if not table:
        print(f"No table found for {country} period {period}")
        return

    for row in table.select("tr"):
        cols = row.select("td")
        if not cols:
            continue

        cols = cols[1:]

        data = []
        event_id = ""

        for col in cols:
            a = col.find("a")

            if a:
                name = a.get_text(strip=True)
                data.append(name)
                href = a.get("href", "")
                match = EVENT_RE.search(href)
                if match:
                    event_id = match.group(1)
            else:
                data.append(col.get_text(strip=True))

        if data and event_id:
            print("|".join(data + [event_id]))
            if int(event_id) not in IMPORTED_TOURNAMENTS:
                name, city, system, start, received = data
                try:
                    start_date = datetime.strptime(start, "%d.%m.%Y").date()
                except ValueError:
                    start_date = datetime.strptime(start, "%Y.%m.%d").date()

                coll.update_one(
                    {"_id": int(event_id)},
                    {"$set": {"country": country, "name": name, "start": start_date}},
                    upsert=True
                )
                scrap_tournament(event_id)
                time.sleep(0.1)


def get_available_periods(country):
    url = f"https://ratings.fide.com/rated_tournaments.phtml?country={country}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    select = soup.select_one("select#archive")

    if not select:
        raise RuntimeError(f"Period selector not found for {country}")

    periods = []

    for option in select.select("option"):
        value = option.get("value", "").strip()

        if value == "current":
            continue

        try:
            period_date = date.fromisoformat(value)
        except ValueError:
            continue

        # if period_date > today or period_date < two_months_ago:
        if period_date < two_months_ago:
            continue

        periods.append(period_date)

    periods.sort(reverse=True)
    return periods


if __name__ == "__main__":
    FEDERATIONS = get_federations()

    for federation in FEDERATIONS:
        try:
            dates = get_available_periods(federation)
        except Exception as e:
            print(f"Error fetching periods for {federation}: {e}")
            continue

        for date_value in dates:
            try:
                scrap_country_period(federation, date_value)
            except Exception as e:
                print(f"Error scrapping {federation}, {date_value}: {e}")
