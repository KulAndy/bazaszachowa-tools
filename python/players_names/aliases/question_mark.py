import re

import mysql.connector

from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS['mysql']
)
mydb.autocommit = True
curs = mydb.cursor()

def main():
    for table in ['all', 'poland']:
        curs.execute(f"""SELECT fullname
        FROM {table}_players
        WHERE fullname LIKE "%?%" """)
        rows = curs.fetchall()
        for row in rows:
            fullname = row[0]
            curs.execute("""SELECT DISTINCT name
            FROM fide_players
            WHERE name LIKE %s """, (re.sub(r"[~?]+", "_", fullname),))
            found = curs.fetchall()
            if len(found) == 1:
                curs.execute("""INSERT IGNORE INTO 
                `subtitutions`(`fullname`, `substitute`)
                VALUES (%s, %s)""", (found[0][0], fullname))
            elif len(found) == 0:
                curs.execute("""SELECT DISTINCT name
                FROM fide_players
                WHERE name LIKE %s """, (re.sub(r"[,.\s~?]+", "%", fullname),))
                found = curs.fetchall()
                if len(found) == 1 and \
                    len(re.sub(r"[,.\s]+", "", fullname)) == \
                    len(re.sub(r"[,.\s]+", "", found[0][0]))  :
                    curs.execute("""INSERT IGNORE INTO 
                    `subtitutions`(`fullname`, `substitute`)
                    VALUES (%s, %s)""", (found[0][0], fullname))
                else:
                    print(fullname, found)


if __name__ == "__main__":
    main()