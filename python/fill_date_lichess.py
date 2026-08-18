import re
from datetime import UTC, date, datetime
from typing import Any, Literal, TypedDict, cast
from urllib.parse import urlparse

import mysql.connector
import requests

from .settings import SETTINGS


class SiteRow(TypedDict):
    siteid: int
    site: str


# ---------------- Lichess API ----------------

BROADCAST_API_BASE = "https://lichess.org/api/broadcast"
STUDY_API_BASE = "https://lichess.org/api/study"
TABLE = "all_games"


# ---------------- Helpers ----------------


def ms_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date()


def resolve_final_url(url: str) -> str:
    r = requests.head(url, allow_redirects=True, timeout=10)
    r.raise_for_status()
    return r.url


# ---------------- Broadcast parsing ----------------


def parse_broadcast_url(
    url: str,
) -> (
    tuple[Literal["tournament"], str]
    | tuple[Literal["tournament"], str, str]
    | tuple[Literal["round"], str, str, str]
    | None
):
    parts = urlparse(url).path.strip("/").split("/")

    if len(parts) == 2 and parts[0] == "broadcast":
        return "tournament", parts[1]

    if len(parts) == 3 and parts[0] == "broadcast":
        return "tournament", parts[2]

    if len(parts) >= 4 and parts[0] == "broadcast":
        return "round", parts[1], parts[2], parts[3]

    return None


def fetch_tournament(tournament_id: str) -> dict[str, Any]:
    r = requests.get(f"{BROADCAST_API_BASE}/{tournament_id}", timeout=15)
    r.raise_for_status()
    return cast(dict[str, Any], r.json())


def fetch_round(tournament_slug: str, round_slug: str, round_id: str) -> dict[str, Any]:
    r = requests.get(
        f"{BROADCAST_API_BASE}/{tournament_slug}/{round_slug}/{round_id}",
        timeout=15,
    )
    r.raise_for_status()
    return cast(dict[str, Any], r.json())


def extract_tournament_date(data: dict[str, Any]) -> date | None:
    tour = data.get("tour", {})
    dates = tour.get("dates")
    if dates:
        return ms_to_date(dates[0])
    if "createdAt" in tour:
        return ms_to_date(tour["createdAt"])
    return None


def extract_round_date(data: dict[str, Any]) -> date | None:
    rnd = data.get("round", {})
    if rnd.get("startsAt"):
        return ms_to_date(rnd["startsAt"])
    if "createdAt" in rnd:
        return ms_to_date(rnd["createdAt"])
    return None


# ---------------- Study parsing ----------------


def parse_study_url(
    url: str,
) -> tuple[Literal["study"], str] | tuple[Literal["chapter"], str, str] | None:
    parts = urlparse(url).path.strip("/").split("/")

    if len(parts) == 2 and parts[0] == "study":
        return "study", parts[1]

    if len(parts) == 3 and parts[0] == "study":
        return "chapter", parts[1], parts[2]

    return None


def fetch_study_pgn(study_id: str, chapter_id: str | None = None) -> str:
    if chapter_id:
        url = f"{STUDY_API_BASE}/{study_id}/{chapter_id}.pgn"
    else:
        url = f"{STUDY_API_BASE}/{study_id}.pgn"

    r = requests.get(
        url,
        params={
            "clocks": "true",
            "comments": "true",
            "variations": "true",
            "orientation": "false",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.text


PGN_DATE_RE = re.compile(r'\[(UTCDate|Date)\s+"(\d{4})\.(\d{2})\.(\d{2})"\]')


def extract_pgn_date(pgn: str) -> tuple[int, int, int] | None:
    for line in pgn.splitlines():
        m = PGN_DATE_RE.match(line)
        if m:
            year, month, day = map(int, m.groups()[1:])
            return year, month, day
    return None


# ---------------- DB ----------------

db = mysql.connector.connect(**SETTINGS["mysql"])
cur = db.cursor(dictionary=True)

cur.execute(f"""
SELECT DISTINCT siteid, site
FROM {TABLE}
JOIN sites ON siteID = sites.id
WHERE Day IS NULL
  AND (
        sites.site LIKE 'https://lichess.org/broadcast/%'
     OR sites.site LIKE 'https://lichess.org/study/%'
  )
""")

rows = cast(list[SiteRow], cur.fetchall())
updates = []

for row in rows:
    siteid = row["siteid"]
    url = row["site"]
    print(url)

    try:
        # ---- Broadcast (direct) ----
        parsed_broadcast = parse_broadcast_url(url)
        match parsed_broadcast:
            case ("tournament", tournament_id):
                data = fetch_tournament(tournament_id)
                game_date = extract_tournament_date(data)

            case ("round", tour_slug, round_slug, round_id):
                data = fetch_round(tour_slug, round_slug, round_id)
                game_date = extract_round_date(data)

            case _:
                game_date = None

        if game_date:
            updates.append((game_date.year, game_date.month, game_date.day, siteid))
        else:
            print("No broadcast date", url)
            continue

        # ---- Study ----
        parsed_study = parse_study_url(url)

        match parsed_study:
            case ("study", study_id):
                try:
                    pgn = fetch_study_pgn(study_id)
                except requests.HTTPError:
                    pgn = ""

            case ("chapter", study_id, chapter_id):
                try:
                    pgn = fetch_study_pgn(study_id, chapter_id)
                except requests.HTTPError:
                    pgn = ""

            case _:
                pgn = ""

        if pgn:
            date_tuple = extract_pgn_date(pgn)

            if date_tuple:
                updates.append((*date_tuple, siteid))
                continue

        print("No PGN date, trying redirect", url)

        # ---- Fallback: follow redirect and retry as broadcast ----
        final_url = resolve_final_url(url)
        redirected_broadcast = parse_broadcast_url(final_url)

        match redirected_broadcast:
            case ("tournament", tournament_id):
                data = fetch_tournament(tournament_id)
                game_date = extract_tournament_date(data)

            case ("round", tour_slug, round_slug, round_id):
                data = fetch_round(tour_slug, round_slug, round_id)
                game_date = extract_round_date(data)

            case _:
                game_date = None

        if game_date:
            updates.append((game_date.year, game_date.month, game_date.day, siteid))
        else:
            print("No broadcast date after redirect", final_url)

    except requests.HTTPError as e:
        print(f"HTTP error {url}: {e}")
    except Exception as e:
        print(f"Error {url}: {e}")

if updates:
    cur.executemany(
        f"""
        UPDATE {TABLE}
        SET
            Year = %s,
            Month = %s,
            Day = %s
        WHERE siteid = %s
          AND Day IS NULL
        """,
        updates,
    )
    db.commit()
    print(f"Updated {cur.rowcount} rows")

cur.close()
db.close()
