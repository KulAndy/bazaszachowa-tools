import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

import mysql.connector
from mysql.connector.abstracts import MySQLConnectionAbstract, MySQLCursorAbstract
from mysql.connector.pooling import PooledMySQLConnection
from unidecode import unidecode

from ..settings import SETTINGS

THREADS = 6
CSV_PATH = "./rejestr_czlonkow.csv"
CSV_ENCODING = "ISO-8859-2"
CSV_DELIMITER = ","

thread_local = threading.local()


def get_connection() -> tuple[
    PooledMySQLConnection | MySQLConnectionAbstract, MySQLCursorAbstract
]:
    if not hasattr(thread_local, "conn"):
        thread_local.conn = mysql.connector.connect(**SETTINGS["mysql"])
        thread_local.cur = thread_local.conn.cursor()

    return thread_local.conn, thread_local.cur


def normalize_key(name: str) -> str:
    return unidecode(name.replace(",", "").strip().lower())


def normalize_csv_name(raw_name: str) -> str:
    raw_name = raw_name.strip()

    parts = raw_name.split()
    if len(parts) < 2:
        return unidecode(raw_name.title())

    lastname = parts[0].capitalize()
    firstname = " ".join(p.capitalize() for p in parts[1:])

    return unidecode(f"{lastname}, {firstname}")


def load_member_registry() -> dict[str, str]:
    registry = {}

    with open(CSV_PATH, encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        for row in reader:
            raw_name = row.get("NAZWISKO_IMIE", "").strip()
            if not raw_name:
                continue

            canonical = normalize_csv_name(raw_name)
            registry[normalize_key(canonical)] = canonical

    print(f"Loaded {len(registry)} names from registry.")
    return registry


def fetch_fullnames() -> list[str]:
    conn = mysql.connector.connect(**SETTINGS["mysql"])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT all_players.fullname
        FROM all_players
        LEFT JOIN subtitutions ON all_players.fullname = subtitutions.substitute
        LEFT JOIN fide_players on all_players.fullname = fide_players.name
        WHERE subtitutions.id IS NULL AND fide_players.fideid IS null
    """)
    names = [
        row[0] for row in cast(list[tuple[str]], cursor.fetchall()) if len(row) > 0
    ]
    cursor.close()
    conn.close()
    return names


def find_matching_name(name: str, registry: dict[str, str]) -> str | None:
    return registry.get(normalize_key(name))


def process_fullname(fullname: str, registry: dict[str, str]) -> None:
    try:
        conn, cur = get_connection()
        parts = fullname.replace(",", " ").split()

        for i in range(len(parts)):
            rotated = " ".join(parts[i:] + parts[:i])
            unified = find_matching_name(rotated, registry)
            if unified:
                if unified.lower() != fullname.lower():
                    print(f"|{fullname}| -> |{unified}|")
                    cur.execute(
                        "INSERT IGNORE INTO subtitutions (fullname, substitute) VALUES (%s, %s)",
                        (unified, fullname),
                    )
                    conn.commit()
                break

    except Exception as e:
        print(f"[ERROR] {fullname}: {e}")


def close_thread_connection() -> None:
    if hasattr(thread_local, "cur"):
        thread_local.cur.close()

    if hasattr(thread_local, "conn"):
        thread_local.conn.close()


if __name__ == "__main__":
    registry = load_member_registry()
    fullnames = fetch_fullnames()
    print(f"Processing {len(fullnames)} Polish player names...")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(process_fullname, name, registry) for name in fullnames
        ]
        for future in as_completed(futures):
            future.result()

    close_thread_connection()
