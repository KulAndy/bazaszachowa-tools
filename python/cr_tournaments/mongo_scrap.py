import html
import logging
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from urllib.parse import quote_plus

import mysql.connector
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from settings import SETTINGS
from unidecode import unidecode

logging.basicConfig(level=logging.INFO)

TMP_ROOT = "tmp"
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

MONGO_URI = (
    f"mongodb://{quote_plus(SETTINGS['mongo']['user'])}:"
    f"{quote_plus(SETTINGS['mongo']['password'])}@"
    f"{SETTINGS['mongo']['host']}:27017/{SETTINGS['mongo']['database']}"
)
MONGO_COLLECTION = "poland_tournaments"

client = MongoClient(MONGO_URI)
db = client[SETTINGS['mongo']['database']]
coll = db[MONGO_COLLECTION]


def get_tournaments_in_base():
    tournaments = db.poland_tournaments.distinct("_id")
    return tournaments


IMPORTED_TOURNAMENTS = get_tournaments_in_base()


def list_files_in_directory(directory):
    return [os.path.join(root, file) for root, dirs, files in os.walk(directory) for file in files]


def sanitize_xml(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            content = file.read()

        entity_pattern = re.compile(r'&#x[0-9A-Fa-f]+;')
        entities = entity_pattern.findall(content)

        for entity in entities:
            unescaped_char = html.unescape(entity)
            content = content.replace(entity, unescaped_char)

        sanitized_content = re.sub(r'[\x00-\x1F\x7F\x80-\x9F]', '', content)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(sanitized_content)
    except Exception as e:
        logging.error(f"Error sanitizing XML file {file_path}: {e}")
        raise


def get_page_url(tournamentid):
    url = f"http://www.cr-pzszach.pl/ew/viewpage.php?page_id=10&id_turnieju={tournamentid}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except Exception as e:
        logging.error(f"Error fetching tournament page {tournamentid}: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    tables = soup.find_all("table")
    if not tables:
        return None

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        last_row = rows[-1]
        cols = last_row.find_all("td")
        if len(cols) != 2:
            continue

        first_col = cols[0].get_text(strip=True)

        if first_col.lower() != "strona www":
            continue

        link_tag = cols[1].find("a")
        if not link_tag:
            continue

        href = link_tag.get("href", "").strip()
        return href

    return None


def process_tournament(args):
    file, url = args
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )
    mydb.autocommit = True
    curs = mydb.cursor()
    tournamentid = os.path.splitext(os.path.basename(file))[0]
    if int(tournamentid) in IMPORTED_TOURNAMENTS:
        logging.info(f"Removed {tournamentid}")
        os.remove(file)
        return

    name, start, end = "", None, None
    logging.info(tournamentid)
    tmp_dir = os.path.join(TMP_ROOT, str(tournamentid))

    try:
        with zipfile.ZipFile(file, 'r') as zip_ref:
            zip_ref.extract("tournament.xml", tmp_dir)
    except Exception as e:
        logging.error(f"Error extracting {file}: {e}")
        os.remove(file)
        return

    tournament_file = os.path.join(tmp_dir, "tournament.xml")

    try:
        sanitize_xml(tournament_file)
        tree = ET.parse(tournament_file)
        root = tree.getroot()
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML file {tournament_file}: {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error processing XML file {tournament_file}: {e}")
        return

    if not url:
        try:
            xml_text = open(tournament_file, "r", encoding="utf-8", errors="ignore").read()
            m = re.search(r"https://www\.chessmanager\.com/pl/tournaments/\d+", xml_text)
            if m:
                url = m.group(0)
        except Exception as e:
            url = get_page_url(tournamentid)

    tour_name_node = root.find(".//tour_name")
    if tour_name_node is not None:
        name = tour_name_node.attrib['value'].strip()

    start_date_node = root.find(".//start_date")
    if start_date_node is not None:
        try:
            year = start_date_node.attrib['year'].strip()
            month = start_date_node.attrib['month'].strip()
            day = start_date_node.attrib['day'].strip()
            start = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
        except:
            pass

    end_date_node = root.find(".//end_date")
    if end_date_node is not None:
        try:
            year = end_date_node.attrib['year'].strip()
            month = end_date_node.attrib['month'].strip()
            day = end_date_node.attrib['day'].strip()
            end = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
        except:
            pass

    url = url or ""

    if not url:
        logging.info("url not found")

    db.poland_tournaments.update_one(
        {"_id": int(tournamentid)},
        {
            "$set": {
                "name": name,
                "start": start,
                "end": end,
                "url": url,
            }
        },
        upsert=True,
    )

    names = []
    for cobarray_item2 in root.findall(".//list_of_players/cobarray_item"):
        rounds = cobarray_item2.findall(".//rounds/cobarray_item")
        if not rounds:
            continue

        has_valid_game = False

        for r in rounds:
            opp_node = r.find("opponent_id")
            pair_node = r.find("pair_no")

            if opp_node is None or pair_node is None:
                continue

            opp = opp_node.attrib.get("value")
            pair = pair_node.attrib.get("value")

            if opp is None or pair is None:
                continue

            if opp != "-1" and pair != "-1":
                has_valid_game = True
                break

        if not has_valid_game:
            continue

        name_surname_node = cobarray_item2.find("name_surname")
        if name_surname_node is not None:
            name_surname = unidecode(name_surname_node.attrib["value"].strip())
            names.append((name_surname,))

    if names:
        curs.executemany("""
            INSERT IGNORE INTO `players`(`fullname`)
            VALUES (%s)
        """, names)

        for name in names:
            curs.execute("""
                SELECT id FROM `players`
                WHERE fullname like %s
            """, name)
            playerid = curs.fetchone()

            db.poland_tournaments.update_one(
                {"_id": int(tournamentid)},
                {"$addToSet": {"players": playerid[0]}},
            )

    os.remove(file)


def import_swsx_s():
    while True:
        dirs = ['swsx', 'swdx', 'sws', 'swd']
        swsx_files = []
        for directory in dirs:
            files = list_files_in_directory(directory)
            for file in files:
                if file.endswith("swsx") or file.endswith("swdx"):
                    process_tournament((file, None))

        if len(swsx_files) == 0:
            break

    if os.path.exists(TMP_ROOT):
        shutil.rmtree(TMP_ROOT)


def scrap_tournaments(year):
    logging.info(f"SCRAPING YEAR: {year}")

    url = f"http://www.cr-pzszach.pl/ew/viewpage.php?page_id=12&rok={year}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except Exception as e:
        logging.error("Request error:", e)
        return
    res.encoding = "ISO-8859-2"

    soup = BeautifulSoup(res.text, "html.parser")

    tables = soup.find_all("table")
    if not tables:
        logging.warning("No tables found")
        return

    EXPECTED_HEADERS = [
        "lp",
        "numer",
        "data rejestr.",
        "data roz./zak.",
        "nazwa turnieju",
        "miejsce",
        "sędzia",
        "www"
    ]

    target_table = None

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["td", "th"])]
        if len(header_cells) == 8 and all(
                h in header_cells for h in EXPECTED_HEADERS
        ):
            target_table = table
            break

    if target_table is None:
        logging.warning("Could not find tournament table")
        return

    rows = target_table.find_all("tr")
    if len(rows) <= 1:
        logging.warning("No tournament data found")
        return

    data = []

    for row in rows[1:]:
        cols = row.find_all("td")
        if not cols:
            continue

        row_values = []

        for col in cols:
            link = col.find("a")
            if link:
                row_values.append(link.get("href", "").strip())
            else:
                row_values.append(col.get_text(strip=True))

        data.append(row_values)
    return data


def extract_scrapped_data(rows):
    for row in rows:
        lp, tournamentid, regeistered, date, card, place, arbiter, url = row
        if int(tournamentid) in IMPORTED_TOURNAMENTS:
            continue
        file = ""
        try:
            res = requests.get(f"http://www.cr-pzszach.pl/ew/ew/swsswd/{tournamentid}.swsx", headers=HEADERS)
            res.raise_for_status()

            filename = f"swsx/{tournamentid}.swsx"
            with open(filename, "wb") as output:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        output.write(chunk)
            file = filename
        except:
            try:
                res = requests.get(f"http://www.cr-pzszach.pl/ew/ew/swsswd/{tournamentid}.swdx", headers=HEADERS)
                res.raise_for_status()

                filename = f"swdx/{tournamentid}.swdx"
                with open(filename, "wb") as output:
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            output.write(chunk)
                file = filename
            except:
                logging.error(f"Cannot download {tournamentid} file")

        if file:
            process_tournament((file, url))


if __name__ == "__main__":
    os.makedirs("swsx", exist_ok=True)
    os.makedirs("swdx", exist_ok=True)

    max_year = datetime.now().year
    min_year = 2010
    if len(sys.argv) > 1:
        max_year = int(sys.argv[1])
        if len(sys.argv) > 2:
            min_year = int(sys.argv[2])

    logging.info(f"{min_year}-{max_year}")

    import_swsx_s()
    IMPORTED_TOURNAMENTS = get_tournaments_in_base()
    for i in range(datetime.now().year, min_year - 1, -1):
        extract_scrapped_data(scrap_tournaments(i))

    db.poland_tournaments.delete_many({"players": {"$exists": True, "$size": 0}})
