import re
import time
from datetime import date, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from settings import SETTINGS

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

FEDERATIONS = [
    "AFG",
    "ALB",
    "ALG",
    "AND",
    "ANG",
    "ANT",
    "ARG",
    "ARM",
    "ARU",
    "AUS",
    "AUT",
    "AZE",
    "BAH",
    "BRN",
    "BAN",
    "BAR",
    "BLR",
    "BEL",
    "BIZ",
    "BER",
    "BHU",
    "BOL",
    "BIH",
    "BOT",
    "BRA",
    "IVB",
    "BRU",
    "BUL",
    "BUR",
    "BDI",
    "CAM",
    "CMR",
    "CAN",
    "CPV",
    "CAY",
    "CAF",
    "CHA",
    "CHI",
    "CHN",
    "TPE",
    "COL",
    "COM",
    "CRC",
    "CIV",
    "CRO",
    "CUB",
    "CYP",
    "CZE",
    "COD",
    "DEN",
    "DJI",
    "DMA",
    "DOM",
    "ECU",
    "EGY",
    "ESA",
    "ENG",
    "GEQ",
    "ERI",
    "EST",
    "SWZ",
    "ETH",
    "FAI",
    "FIJ",
    "FIN",
    "FRA",
    "GAB",
    "GAM",
    "GEO",
    "GER",
    "GHA",
    "GRE",
    "GRL",
    "GRN",
    "GUM",
    "GUA",
    "GCI",
    "GUY",
    "HAI",
    "HON",
    "HKG",
    "HUN",
    "ISL",
    "IND",
    "INA",
    "IRI",
    "IRQ",
    "IRL",
    "IOM",
    "ISR",
    "ITA",
    "JAM",
    "JPN",
    "JCI",
    "JOR",
    "KAZ",
    "KEN",
    "KOS",
    "KUW",
    "KGZ",
    "LAO",
    "LAT",
    "LBN",
    "LES",
    "LBR",
    "LBA",
    "LIE",
    "LTU",
    "LUX",
    "MAC",
    "MAD",
    "MAW",
    "MAS",
    "MDV",
    "MLI",
    "MLT",
    "MTN",
    "MRI",
    "MEX",
    "MDA",
    "MNC",
    "MGL",
    "MNE",
    "MAR",
    "MOZ",
    "MYA",
    "NAM",
    "NRU",
    "NEP",
    "NED",
    "AHO",
    "NCL",
    "NZL",
    "NCA",
    "NIG",
    "NGR",
    "MKD",
    "NOR",
    "OMA",
    "PAK",
    "PLW",
    "PLE",
    "PAN",
    "PNG",
    "PAR",
    "PER",
    "PHI",
    "POL",
    "POR",
    "PUR",
    "QAT",
    "ROU",
    "RUS",
    "RWA",
    "SKN",
    "LCA",
    "VIN",
    "SMR",
    "STP",
    "KSA",
    "SCO",
    "SEN",
    "SRB",
    "SEY",
    "SLE",
    "SGP",
    "SVK",
    "SLO",
    "SOL",
    "SOM",
    "RSA",
    "KOR",
    "SSD",
    "ESP",
    "SRI",
    "SUD",
    "SUR",
    "SWE",
    "SUI",
    "SYR",
    "TJK",
    "TAN",
    "THA",
    "TLS",
    "TOG",
    "TGA",
    "TTO",
    "TUN",
    "TUR",
    "TKM",
    "UGA",
    "UKR",
    "UAE",
    "USA",
    "URU",
    "ISV",
    "UZB",
    "VAN",
    "VEN",
    "VIE",
    "WLS",
    "YEM",
    "ZAM",
    "ZIM"
]
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
                start_date = datetime.strptime(start, "%d.%m.%Y").date()
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
