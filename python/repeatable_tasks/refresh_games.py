import argparse
import logging
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import mysql.connector

from . import PGN_DIR, DOWNLOAD_DIR, CPP_BIN_DIR, IMPORT_TABLE, ALL_GAMES_TABLE
from .scrap_chessbase import scrap_chessbase
from .scrap_lichess import scrap_lichess
from .scrap_twic import scrap_twic
from .utils import concat_pgns
from .. import settings, removeDuplicates, removeSimilar, decode_data
from ..players_names.fill_import import fill_event, fill_sites, fill_black, fill_white

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--twic",
        action="store_true",
        help="Download TWIC games"
    )

    parser.add_argument(
        "--chessbase",
        action="store_true",
        help="Download ChessBase games"
    )

    parser.add_argument(
        "--lichess",
        action="store_true",
        help="Download Lichess games"
    )

    args = parser.parse_args()

    if not (args.twic or args.chessbase or args.lichess):
        parser.error("at least one of --twic, --chessbase, or --lichess is required")
    logging.basicConfig(level=logging.ERROR)
    RETRIES = 5
    if args.twic:
        scrap_twic()

    if args.lichess:
        scrap_lichess()

    if args.chessbase:
        scrap_chessbase()

    concat_pgns(PGN_DIR)

    subprocess.run(
        [str(CPP_BIN_DIR / "prepare_pgn"), "concat.pgn"],
        cwd=PGN_DIR,
        capture_output=True,
    )
    subprocess.run(
        [str(CPP_BIN_DIR / "pgn2sql"), "clean.pgn", IMPORT_TABLE],
        cwd=PGN_DIR,
        capture_output=True,
    )

    mydb = mysql.connector.connect(
        **settings.SETTINGS["mysql"],
        autocommit=True
    )
    curs = mydb.cursor()

    curs.execute(f"TRUNCATE TABLE `{IMPORT_TABLE}`")
    mydb.commit()
    mydb.autocommit = True

    with open(PGN_DIR / "insert.sql") as f:
        for line in f.readlines():
            if not "0x," in line:
                curs.execute(line)

    today = datetime.today()
    min_year = today.year
    if today.month == 1:
        min_year = today.year - 1

    curs.execute(f"""DELETE FROM `{IMPORT_TABLE}`
                    WHERE Year < %s""", (min_year,))

    for i in range(RETRIES):
        with ThreadPoolExecutor() as executor:
            executor.submit(fill_event, "all")
            executor.submit(fill_sites, "all")
            executor.submit(fill_white, "all")
            executor.submit(fill_black, "all")

        curs.execute(f"""SELECT
                COUNT(*),
                COUNT(eventID),
                COUNT(siteID),
                COUNT(WhiteID),
                COUNT(BlackID)
            FROM `{IMPORT_TABLE}`
        """)
        all, events, sites, white, black = curs.fetchone()
        if all - events == 0 \
                and all - sites == 0 \
                and all - white == 0 \
                and all - black == 0:
            break
        elif i == RETRIES - 1:
            logging.error(f"Unable to normalize")
            sys.exit(1)



    for i in range(RETRIES):
        subprocess.run(
            [str(CPP_BIN_DIR / "lichess_classify"), IMPORT_TABLE],
            cwd=PGN_DIR,
            capture_output=True,
        )
        curs.execute(f"""SELECT
                COUNT(*),
                COUNT(ecoID)
            FROM `{IMPORT_TABLE}`
        """)
        all, eco = curs.fetchone()
        if all - eco == 0:
            break
        elif i == RETRIES - 1:
            logging.error("Unalble to classify")
            sys.exit(1)

    curs.execute(f"""INSERT INTO `{ALL_GAMES_TABLE}`
    (`moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`,
    `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID`)

    SELECT `moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`,
    `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID`
    FROM {IMPORT_TABLE}
""")
    curs.execute(f"TRUNCATE TABLE `{IMPORT_TABLE}`")

    mydb.commit()
    mydb.close()

    shutil.rmtree(PGN_DIR, ignore_errors=True)
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)

    decode_data.decode_events()
    decode_data.decode_sites()
    decode_data.decode_players()

    removeDuplicates.main("all")
    removeSimilar.main("all")
