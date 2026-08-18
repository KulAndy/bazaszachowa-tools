import sys
from concurrent.futures import ThreadPoolExecutor

import mysql.connector

from .. import settings


def fill_sites(table):
    mydb = mysql.connector.connect(**settings.SETTINGS["mysql"])

    mydb.autocommit = True
    cursor = mydb.cursor()
    cursor.execute(f"""INSERT IGNORE INTO sites(Site)
                        SELECT DISTINCT Site FROM `import_{table}`""")

    query = f"""SELECT Id, site FROM `sites` WHERE site in (SELECT site FROM import_{table} WHERE siteID IS NULL) ORDER BY id"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{table} set siteID = %s WHERE site = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_event(table):
    mydb = mysql.connector.connect(**settings.SETTINGS["mysql"])

    mydb.autocommit = True
    cursor = mydb.cursor()
    cursor.execute(f"""INSERT IGNORE INTO chess_events(name)
                        SELECT DISTINCT Event FROM `import_{table}`""")

    query = f"""SELECT Id, name FROM chess_events WHERE name in (SELECT event FROM import_{table} WHERE eventID IS NULL) ORDER BY id"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{table} set eventID = %s WHERE event = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_white(table):
    mydb = mysql.connector.connect(**settings.SETTINGS["mysql"])

    mydb.autocommit = True
    cursor = mydb.cursor()
    cursor.execute(f"""INSERT IGNORE INTO players(fullname)
                        SELECT DISTINCT white as player FROM `import_{table}`""")

    query = f"""SELECT Id, fullname FROM players WHERE fullname in (SELECT white FROM import_{table} WHERE WhiteID IS NULL) ORDER BY id"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{table} set WhiteID = %s WHERE white = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_black(table):
    mydb = mysql.connector.connect(**settings.SETTINGS["mysql"])

    mydb.autocommit = True
    cursor = mydb.cursor()
    cursor.execute(f"""INSERT IGNORE INTO players(fullname)
                        SELECT DISTINCT Black as player FROM `import_{table}`""")

    query = f"""SELECT Id, fullname FROM players WHERE fullname in (SELECT black FROM import_{table} WHERE BlackID IS NULL) ORDER BY id"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{table} set BlackID = %s WHERE black = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


if __name__ == "__main__":
    try:
        TABLE = sys.argv[1]
    except IndexError:
        TABLE = "all"

    with ThreadPoolExecutor() as executor:
        executor.submit(fill_event, "all")
        executor.submit(fill_sites, "all")
        executor.submit(fill_white, "all")
        executor.submit(fill_black, "all")
