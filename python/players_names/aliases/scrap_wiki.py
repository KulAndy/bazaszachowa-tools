import re
import logging
import requests
import unidecode
from bs4 import BeautifulSoup
import mysql.connector

from settings import SETTINGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("wiki-scraper")

mydb = mysql.connector.connect(**SETTINGS["mysql"])
mydb.autocommit = True
curs = mydb.cursor()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; wiki-scraper/1.0)"
}

IGNORE_LINKS = [
    "/wiki/Szachy",
    "/wiki/Zwi%C4%85zek_Socjalistycznych_Republik_Socjalistycznych"
]

visited = set()


def fetch(url):
    try:
        log.debug(f"GET {url}")
        r = requests.get(url, headers=HEADERS, timeout=15)

        log.debug(f"STATUS {r.status_code} | {url}")

        if r.status_code != 200:
            log.warning(f"Bad response: {url}")
            return None

        return r

    except Exception as e:
        log.error(f"Request error {url} -> {e}")
        return None


# ----------------------------
# SCRAPER
# ----------------------------
def scrap_wiki(url, base_url, depth=0):
    indent = "  " * depth

    if url in visited:
        log.debug(f"{indent}SKIP VISITED {url}")
        return []

    visited.add(url)
    log.debug(f"{indent}SCRAP: {url}")

    response = fetch(url)
    if not response:
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    substitutions = []

    links = [
        a["href"]
        for a in soup.find_all("a", href=True)
        if not a.find_parent("div", class_="catlinks")
    ]

    log.info(f"{indent}FOUND LINKS: {len(links)}")

    categories = [
        x for x in links
        if x.startswith("/wiki/Kategoria:")
    ]

    log.info(f"{indent}CATEGORIES: {len(categories)}")

    for category in categories:
        full_cat_url = f"{base_url}{category}"
        substitutions += scrap_wiki(full_cat_url, base_url, depth + 1)

    page_links = [
        str(x) for x in links
        if x.startswith("/wiki/")
        and ":" not in x
        and x not in IGNORE_LINKS
    ]

    log.info(f"{indent}PAGE LINKS: {len(page_links)}")

    for link in page_links:
        full_url = link if link.startswith("http") else f"{base_url}{link}"

        if full_url in visited:
            log.debug(f"{indent}SKIP VISITED PAGE {full_url}")
            continue

        visited.add(full_url)

        log.debug(f"{indent}VISITING PAGE {full_url}")

        response = fetch(full_url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        pl_title_tag = soup.find("h1")
        polish_title = pl_title_tag.get_text(strip=True) if pl_title_tag else None

        log.info(f"{indent}PL TITLE: {polish_title}")

        english_link_tag = soup.select_one('a[hreflang="en"]')

        if not english_link_tag:
            log.warning(f"{indent}NO EN LINK: {polish_title}")
            continue

        english_url = english_link_tag.get("href")
        if not english_url:
            log.warning(f"{indent}EN LINK WITHOUT HREF: {polish_title}")
            continue

        if english_url.startswith("/"):
            english_url = "https://en.wikipedia.org" + english_url

        en_resp = fetch(english_url)
        if not en_resp:
            continue

        soup = BeautifulSoup(en_resp.text, "html.parser")

        en_title_tag = soup.find("h1")
        english_title = en_title_tag.get_text(strip=True) if en_title_tag else None

        log.info(f"{indent}EN TITLE: {english_title}")

        polish_name = re.sub(r"\(.*\)$", "", polish_title or "").strip()
        polish_name = re.sub(r"\s+", " ", polish_name)

        english_name = re.sub(r"\(.*\)$", "", english_title or "").strip()
        english_name = re.sub(r"\s+", " ", english_name)

        log.info(f"{indent}PARSED PL: {polish_name}")
        log.info(f"{indent}PARSED EN: {english_name}")

        if polish_name.count(" ") != 1 or english_name.count(" ") != 1:
            log.warning(
                f"{indent}INVALID NAME FORMAT: |{polish_name}|{english_name}|"
            )
            continue

        pl_first, pl_last = polish_name.split(" ")
        en_first, en_last = english_name.split(" ")

        substitutions.append((
            unidecode.unidecode(f"{en_last}, {en_first}"),
            f"{pl_last}, {pl_first}",
        ))

        substitutions.append((
            unidecode.unidecode(f"{en_last}, {en_first}"),
            unidecode.unidecode(f"{pl_last}, {pl_first}"),
        ))

    return substitutions


# ----------------------------
# MAIN
# ----------------------------
def main():
    log.info("START SCRAPING")

    substitutions = []

    seeds = [
        "https://pl.wikipedia.org/wiki/Kategoria:Szachi%C5%9Bci_wed%C5%82ug_narodowo%C5%9Bci",
        "https://pl.wikipedia.org/wiki/Kategoria:Szachi%C5%9Bci_XXI_wieku",
        "https://pl.wikipedia.org/wiki/Kategoria:Szachi%C5%9Bci_XX_wieku",
    ]

    for url in seeds:
        substitutions += scrap_wiki(url, "https://pl.wikipedia.org")

    log.info(f"RAW RESULTS: {len(substitutions)}")

    substitutions = list(filter(lambda x: x[0] != x[1], substitutions))

    log.info(f"AFTER FILTER: {len(substitutions)}")

    for s in substitutions:
        log.info(s)

    if substitutions:
        curs.executemany(
            """
            INSERT IGNORE INTO `subtitutions` (`fullname`, `substitute`)
            VALUES (%s, %s)
            """,
            substitutions,
        )

    log.info("DONE")


if __name__ == "__main__":
    main()