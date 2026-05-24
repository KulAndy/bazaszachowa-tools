import re
import unicodedata

import mysql.connector
from unidecode import unidecode

from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS["mysql"]
)
curs = mydb.cursor()


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(
        r'[\x00-\x1F\x7F-\x9F]',
        '',
        text
    )

    text = unidecode(text)
    text = re.sub(
        r'[\u200B-\u200D\uFEFF\u00A0]',
        '',
        text
    )

    return text.strip()


def decode_events():
    curs.execute(r"""SELECT name 
    FROM `chess_events` 
    WHERE `name` REGEXP '[^\\x20-\\x7F]' """)
    rows = curs.fetchall()

    decoded = []
    to_replace = []

    for row in rows:
        event, = row
        decoded_event = clean_text(event)
        decoded.append((decoded_event,))
        to_replace.append((decoded_event, event))

    curs.executemany("""INSERT IGNORE chess_events(name)
    VALUES (%s)
    """, decoded)
    curs.executemany("""UPDATE IGNORE chess_events
    SET name = %s
    WHERE  name = %s
    """, to_replace)

    curs.executemany("""
    UPDATE all_games
    SET eventID = ( SELECT id FROM chess_events WHERE name = %s )
    WHERE eventID IN ( SELECT id FROM chess_events WHERE name = %s )
    """, to_replace)

    curs.executemany("""
    UPDATE poland_games
    SET eventID = ( SELECT id FROM chess_events WHERE name = %s )
    WHERE eventID IN ( SELECT id FROM chess_events WHERE name = %s )
    """, to_replace)

    mydb.commit()


def decode_sites():
    curs.execute(r"""SELECT site
        FROM sites
        WHERE site REGEXP '[^\\x20-\\x7F]' """)
    rows = curs.fetchall()

    decoded = []
    to_replace = []

    for row in rows:
        site, = row
        decoded_site = clean_text(site)
        decoded.append((decoded_site,))
        to_replace.append((decoded_site, site))

    curs.executemany("""INSERT IGNORE sites(site)
    VALUES (%s)
    """, decoded)
    curs.executemany("""UPDATE IGNORE sites
    SET site = %s
    WHERE  site = %s
    """, to_replace)

    curs.executemany("""
    UPDATE all_games
    SET siteID = ( SELECT id FROM sites WHERE site = %s )
    WHERE siteID IN ( SELECT id FROM sites WHERE site = %s )
    """, to_replace)

    curs.executemany("""
    UPDATE poland_games
    SET siteID = ( SELECT id FROM sites WHERE site = %s )
    WHERE siteID IN ( SELECT id FROM sites WHERE site = %s )
    """, to_replace)

    mydb.commit()


def decode_players():
    curs.execute(r"""SELECT fullname 
    FROM `players` 
    WHERE `fullname` REGEXP '[^\\x20-\\x7F]' """)
    rows = curs.fetchall()

    decoded = []
    to_replace = []

    for row in rows:
        player, = row
        decoded_player = clean_text(player)
        decoded.append((decoded_player,))
        to_replace.append((decoded_player, player))

    curs.executemany("""INSERT IGNORE players(fullname)
    VALUES (%s)
    """, decoded)
    curs.executemany("""UPDATE IGNORE players
    SET fullname = %s
    WHERE  fullname = %s
    """, to_replace)

    curs.executemany("""INSERT IGNORE INTO `subtitutions`(`fullname`, `substitute`) 
    VALUES (%s, %s)""", to_replace)

    curs.executemany("""
    UPDATE all_games
    SET whiteID = ( SELECT id FROM players WHERE fullname = %s )
    WHERE whiteID IN ( SELECT id FROM players WHERE fullname = %s )
    """, to_replace)
    curs.executemany("""
    UPDATE all_games
    SET blackID = ( SELECT id FROM players WHERE fullname = %s )
    WHERE blackID IN ( SELECT id FROM players WHERE fullname = %s )
    """, to_replace)

    curs.executemany("""
    UPDATE poland_games
    SET whiteID = ( SELECT id FROM players WHERE fullname = %s )
    WHERE whiteID IN ( SELECT id FROM players WHERE fullname = %s )
    """, to_replace)
    curs.executemany("""
    UPDATE poland_games
    SET blackID = ( SELECT id FROM players WHERE fullname = %s )
    WHERE blackID IN ( SELECT id FROM players WHERE fullname = %s )
    """, to_replace)

    mydb.commit()


if __name__ == "__main__":
    print("decode_events")
    decode_events()
    print("decode_sites")
    decode_sites()
    print("decode_players")
    decode_players()
