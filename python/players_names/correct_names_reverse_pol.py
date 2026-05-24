import csv
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import mysql.connector
from settings import SETTINGS
from unidecode import unidecode

THREADS = 6
CSV_PATH = "./rejestr_czlonkow.csv"
CSV_ENCODING = "ISO-8859-2"
CSV_DELIMITER = ","

punctuation_pattern = re.compile(r"[^\w]+", re.UNICODE)


def load_member_registry():
    registry = set()

    with open(CSV_PATH, "r", encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        for row in reader:
            raw_name = row.get("NAZWISKO_IMIE", "").strip()
            if not raw_name:
                continue

            normalized = normalize_csv_name(raw_name)
            registry.add(normalized)

    print(f"Loaded {len(registry)} names from registry.")
    return registry


def normalize_csv_name(raw_name: str) -> str:
    raw_name = raw_name.strip()
    parts = raw_name.split()
    if len(parts) < 2:
        return unidecode(raw_name.title())

    lastname = parts[0].capitalize()
    firstname = " ".join(p.capitalize() for p in parts[1:])
    unified = f"{lastname}, {firstname}"

    return unidecode(unified)


def fetch_fullnames():
    conn = mysql.connector.connect(**SETTINGS["mysql"])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT all_players.fullname
        FROM all_players
        LEFT JOIN subtitutions ON all_players.fullname = subtitutions.substitute
        LEFT JOIN fide_players on all_players.fullname = fide_players.name
        WHERE subtitutions.id IS NULL AND fide_players.fideid IS null
    """)
    names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return names


def process_fullname(fullname: str, registry: set):
    conn = None
    cur = None
    try:
        conn = mysql.connector.connect(**SETTINGS["mysql"])
        cur = conn.cursor()

        parts = re.split(r"[\s,]+", fullname.strip())
        if len(parts) < 2:
            return

        unified = find_matching_name(fullname, registry)
        if unified:
            if unified != fullname and unified.lower() != fullname.lower():
                print(f"|{fullname}| > |{unified}|")
                cur.execute(
                    "INSERT IGNORE INTO subtitutions (fullname, substitute) VALUES (%s, %s)",
                    (unified, fullname)
                )
                conn.commit()
            return

        for i in range(1, len(parts)):
            rotated = " ".join(parts[i:] + parts[:i])
            unified = find_matching_name(rotated, registry)
            if unified:
                if unified != fullname and unified.lower() != fullname.lower():
                    print(f"|{fullname}| > |{unified}|")
                    cur.execute(
                        "INSERT IGNORE INTO subtitutions (fullname, substitute) VALUES (%s, %s)",
                        (unified, fullname)
                    )
                    conn.commit()
                break

    except Exception as e:
        print(f"[ERROR] {fullname}: {e}")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def find_matching_name(name: str, registry: set) -> str | None:
    normalized = unidecode(name.replace(",", "").strip().title())

    for reg_name in registry:
        if normalized.replace(",", "").lower() == reg_name.replace(",", "").lower():
            return reg_name
    return None


if __name__ == "__main__":
    registry = load_member_registry()
    fullnames = fetch_fullnames()
    print(f"Processing {len(fullnames)} Polish player names...")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(process_fullname, name, registry) for name in fullnames]
        for future in as_completed(futures):
            future.result()
