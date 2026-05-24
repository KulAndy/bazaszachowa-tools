import sys
from concurrent.futures import ThreadPoolExecutor

import mysql.connector
from settings import SETTINGS

try:
    TABLE = sys.argv[1]
except IndexError:
    TABLE = "all"


def fill_eco():
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )

    mydb.autocommit = True
    cursor = mydb.cursor()

    print("eco update")
    query = f"""SELECT Id, ECO FROM eco WHERE eco in (SELECT eco FROM import_{TABLE} WHERE ecoId IS NULL)"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{TABLE} set ecoID = %s WHERE eco = %s", rows)
    mydb.commit()

    cursor.close()
    mydb.close()


def fill_sites():
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )

    mydb.autocommit = True
    cursor = mydb.cursor()
    print("site update")
    query = f"""SELECT Id, site FROM `sites` WHERE site in (SELECT site FROM import_{TABLE} WHERE siteID IS NULL)"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{TABLE} set siteID = %s WHERE site = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_event():
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )

    mydb.autocommit = True
    cursor = mydb.cursor()
    print("event update")
    query = f"""SELECT Id, name FROM chess_events WHERE name in (SELECT event FROM import_{TABLE} WHERE eventID IS NULL)"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{TABLE} set eventID = %s WHERE event = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_white():
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )

    mydb.autocommit = True
    cursor = mydb.cursor()
    print("white update")
    query = f"""SELECT Id, fullname FROM players WHERE fullname in (SELECT white FROM import_{TABLE} WHERE WhiteID IS NULL)"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{TABLE} set WhiteID = %s WHERE white = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


def fill_black():
    mydb = mysql.connector.connect(
        **SETTINGS["mysql"]
    )

    mydb.autocommit = True
    cursor = mydb.cursor()
    print("black update")
    query = f"""SELECT Id, fullname FROM players WHERE fullname in (SELECT black FROM import_{TABLE} WHERE BlackID IS NULL)"""
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.executemany(f"UPDATE import_{TABLE} set BlackID = %s WHERE black = %s", rows)
    mydb.commit()
    cursor.close()
    mydb.close()


if __name__ == "__main__":
    with ThreadPoolExecutor() as executor:
        executor.submit(fill_eco)
        executor.submit(fill_event)
        executor.submit(fill_sites)
        executor.submit(fill_white)
        executor.submit(fill_black)
