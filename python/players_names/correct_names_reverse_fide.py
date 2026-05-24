import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import mysql.connector
from settings import SETTINGS
from unidecode import unidecode

THREADS = 6
BATCH_SIZE = 500

punctuation_pattern = re.compile(r"[^\w]+", re.UNICODE)


def process_fullname(fullname):
    conn = None
    cur = None
    try:
        conn = mysql.connector.connect(**SETTINGS["mysql"])
        cur = conn.cursor()
        fullname = unidecode(fullname)
        parts = re.split(r"[\s,]+", fullname.strip())

        if len(parts) < 2:
            return

        canonical_first = parts[0]
        canonical_regex = r'^' + r'([\s,]+)'.join(map(re.escape, parts)) + r'$'

        cur.execute("""
            SELECT distinct name FROM fide_players 
            WHERE name LIKE %s AND name REGEXP %s 
        """, (canonical_first + '%', canonical_regex))
        if rows := cur.fetchall():
            if len(rows) == 1:
                row = rows[0]
                fide_name = row[0]
                if fide_name != fullname:
                    print(f"|{fullname}| > |{fide_name}|")
                    if fide_name.lower() == fullname.lower():
                        cur.execute(
                            "UPDATE `players` "
                            "SET `fullname` = %s "
                            "WHERE `players`.`fullname` = %s",
                            (fide_name, fullname)
                        )

                    else:
                        cur.execute(
                            "INSERT IGNORE INTO "
                            "subtitutions (fullname, substitute) "
                            "VALUES (%s, %s)",
                            (fide_name, fullname)
                        )
                    conn.commit()
            return

        for i in range(1, len(parts)):
            rotated_parts = parts[i:] + parts[:i]

            first_part = rotated_parts[0]
            regex_pattern = r"^" + r"([\s,]+)".join(map(re.escape, rotated_parts)) + r"$"

            cur.execute(
                """
                SELECT distinct name FROM fide_players 
                WHERE name LIKE %s AND name REGEXP %s 
                """,
                (first_part + '%', regex_pattern)
            )
            rows = cur.fetchall()
            if len(rows) == 1:
                row = rows[0]
                print(f"|{fullname}| > |{row[0]}|")
                cur.execute(
                    "INSERT IGNORE INTO subtitutions (fullname, substitute) VALUES (%s, %s)",
                    (row[0], fullname)
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


def fetch_fullnames():
    conn = mysql.connector.connect(
        **SETTINGS["mysql"]
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT all_players.fullname
        FROM all_players
        LEFT JOIN subtitutions ON all_players.fullname = subtitutions.substitute
        LEFT JOIN fide_players ON all_players.fullname = fide_players.name
        WHERE subtitutions.id IS NULL AND fide_players.fideid IS NULL    
        """)
    all_names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return all_names


if __name__ == "__main__":
    fullnames = fetch_fullnames()

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(process_fullname, name) for name in fullnames]
        for future in as_completed(futures):
            future.result()
