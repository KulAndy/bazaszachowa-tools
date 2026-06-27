import re
import asyncio
from datetime import date, datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from playwright.async_api import async_playwright
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

EVENT_RE = re.compile(r"/report\.phtml\?event=(\d+)")

SEM = asyncio.Semaphore(10)


def get_tournaments_in_base(country):
    docs = coll.find({"country": country}, {"_id": 1})
    return [doc["_id"] for doc in docs]


async def fetch_html(page, url):
    await page.goto(url, wait_until="networkidle")
    return await page.content()


async def scrap_tournament(context, event_id):
    async with SEM:
        page = await context.new_page()
        url = f"https://ratings.fide.com/report.phtml?event={event_id}"

        html = await fetch_html(page, url)
        await page.close()

        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.table2")

        if not table:
            raise RuntimeError("table.table2 not found")

        players = []
        for row in table.select("tr")[1:]:
            cells = row.select("td")
            if len(cells) < 9:
                continue

            player_id = cells[0].get_text(strip=True)
            if player_id.isdigit():
                players.append(int(player_id))

        coll.update_one(
            {"_id": int(event_id)},
            {"$set": {"players": players}},
            upsert=True,
        )


async def scrap_country_period(context, country, period):
    IMPORTED_TOURNAMENTS = get_tournaments_in_base(country)

    url = f"https://ratings.fide.com/rated_tournaments.phtml?country={country}&period={period}"
    print(url)

    async with SEM:
        page = await context.new_page()
        html = await fetch_html(page, url)
        await page.close()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#main_table")
    if not table:
        print(f"No table found for {country} period {period}")
        return

    tasks = []

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
                    start_date = datetime.strptime(start, "%d.%m.%Y")
                except:
                    try:
                        start_date = datetime.strptime(start, "%Y-%m-%d")
                    except:
                        start_date = datetime.strptime(start, "%Y.%m.%d")

                coll.update_one(
                    {"_id": int(event_id)},
                    {"$set": {"country": country, "name": name, "start": start_date}},
                    upsert=True
                )

                tasks.append(scrap_tournament(context, event_id))

    await asyncio.gather(*tasks)


async def get_available_periods(context, country):
    url = f"https://ratings.fide.com/rated_tournaments.phtml?country={country}"

    page = await context.new_page()
    html = await fetch_html(page, url)
    await page.close()

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

        if period_date < two_months_ago:
            continue

        periods.append(period_date)

    return sorted(periods, reverse=True)


async def get_federations(context):
    url = "https://ratings.fide.com/rated_tournaments.phtml"

    page = await context.new_page()
    html = await fetch_html(page, url)
    await page.close()

    soup = BeautifulSoup(html, "html.parser")
    select = soup.select_one("#select_country")

    return [
        o.get("value").strip()
        for o in select.select("option")
        if o.get("value", "").strip()
    ]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context()

        federations = await get_federations(context)

        for federation in federations:
            try:
                periods = await get_available_periods(context, federation)
            except Exception as e:
                print(f"period error {federation}: {e}")
                continue

            for period in periods:
                try:
                    await scrap_country_period(context, federation, period)
                except Exception as e:
                    print(f"scrape error {federation} {period}: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
