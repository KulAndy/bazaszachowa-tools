import time

import mysql.connector
import requests

from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS["mysql"]
)


def url_exists(url, timeout=5):
    try:
        r = requests.get(
            url,
            allow_redirects=True,
            timeout=timeout,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )
        return r.status_code < 400
    except requests.RequestException:
        return False


def main():
    curs = mydb.cursor()
    curs.execute(r"""SELECT site 
    FROM `sites` 
    WHERE 
    `site` LIKE 'http%'
    and not site regexp "https://lichess.org/broadcast/[\\w-]+/\\w{8}"
    ORDER BY site""")

    rows = curs.fetchall()
    with open("out.txt", "w") as f:
        for row in rows:
            site = row[0]
            if not url_exists(site):
                print(site)
                f.write(site + "\n")
            time.sleep(1)


if __name__ == "__main__":
    main()
