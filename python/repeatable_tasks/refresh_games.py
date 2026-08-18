import argparse
import logging
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import cast

import mysql.connector

from .. import decode_data, removeDuplicates, removeSimilar, settings
from ..players_names.fill_import import fill_black, fill_event, fill_sites, fill_white
from . import (
    ALL_GAMES_TABLE,
    CPP_BIN_DIR,
    DOWNLOAD_DIR,
    IMPORT_TABLE,
    PGN_DIR,
    POLAND_GAMES_TABLE,
)
from .scrap_chessbase import scrap_chessbase
from .scrap_chessresults import scrap_chessresult
from .scrap_lichess import scrap_lichess
from .scrap_poland import scrap_poland
from .scrap_twic import scrap_twic
from .utils import concat_pgns

RETRIES = 5

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--twic",
        action="store_true",
        help="Download TWIC games",
    )

    parser.add_argument(
        "--chessbase",
        action="store_true",
        help="Download ChessBase games",
    )

    parser.add_argument(
        "--lichess",
        action="store_true",
        help="Download Lichess games",
    )

    parser.add_argument(
        "--poland",
        action="store_true",
        help="Download poland games and add also to poland database",
    )

    parser.add_argument(
        "--chessresult",
        action="store_true",
        help="Download chess results games",
    )

    args = parser.parse_args()

    if not (
        args.twic or args.chessbase or args.lichess or args.poland or args.chessresult
    ):
        parser.error(
            "at least one of --twic, --chessbase, --lichess, "
            "--poland or --chessresult is required"
        )
    logging.basicConfig(level=logging.ERROR)
    if args.twic:
        scrap_twic()

    if args.lichess:
        scrap_lichess()

    if args.chessbase:
        scrap_chessbase()

    if args.poland:
        scrap_poland()

    if args.chessresult:
        scrap_chessresult()

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
        autocommit=True,
    )

    curs = mydb.cursor()

    curs.execute(f"TRUNCATE TABLE `{IMPORT_TABLE}`")
    mydb.commit()

    with open(PGN_DIR / "insert.sql") as f:
        for line in f.readlines():
            if "0x," not in line:
                curs.execute(line)
    mydb.commit()

    today = datetime.today()
    min_year = today.year
    if today.month == 1:
        min_year = today.year - 1

    curs.execute(
        f"""
        DELETE FROM `{IMPORT_TABLE}`
        WHERE Year < %s
        """,
        (min_year,),
    )

    for i in range(RETRIES):
        with ThreadPoolExecutor() as executor:
            executor.submit(fill_event, "all")
            executor.submit(fill_sites, "all")
            executor.submit(fill_white, "all")
            executor.submit(fill_black, "all")

        row = curs.fetchone()

        row = curs.fetchone()

        if row is None:
            logging.error("Unable to retrieve normalization statistics")
            sys.exit(1)

        total, events, sites, white, black = cast(
            tuple[int, int, int, int, int],
            row,
        )

        if total == events == sites == white == black:
            break

        if i == RETRIES - 1:
            logging.error("Unable to normalize")
            sys.exit(1)

    for i in range(RETRIES):
        subprocess.run(
            [str(CPP_BIN_DIR / "lichess_classify"), IMPORT_TABLE],
            cwd=PGN_DIR,
            capture_output=True,
        )

        curs.execute(
            f"""
            SELECT
                COUNT(*),
                COUNT(ecoID)
            FROM `{IMPORT_TABLE}`
            """
        )

        row = curs.fetchone()

        if row is None:
            logging.error("Unable to retrieve classification statistics")
            sys.exit(1)

        total, eco = cast(tuple[int, int], row)

        if total == eco:
            break

        if i == RETRIES - 1:
            logging.error("Unable to classify")
            sys.exit(1)

    curs.execute(
        f"""
        INSERT INTO `{ALL_GAMES_TABLE}`
        (
            `moves_blob`,
            `eventID`,
            `siteID`,
            `Year`,
            `Month`,
            `Day`,
            `Round`,
            `WhiteID`,
            `BlackID`,
            `Result`,
            `WhiteElo`,
            `BlackElo`,
            `ecoID`
        )
        SELECT
            `moves_blob`,
            `eventID`,
            `siteID`,
            `Year`,
            `Month`,
            `Day`,
            `Round`,
            `WhiteID`,
            `BlackID`,
            `Result`,
            `WhiteElo`,
            `BlackElo`,
            `ecoID`
        FROM `{IMPORT_TABLE}`
        """
    )

    if args.poland:
        curs.execute(
            f"""
            INSERT INTO `{POLAND_GAMES_TABLE}`
            (
                `moves_blob`,
                `eventID`,
                `siteID`,
                `Year`,
                `Month`,
                `Day`,
                `Round`,
                `WhiteID`,
                `BlackID`,
                `Result`,
                `WhiteElo`,
                `BlackElo`,
                `ecoID`
            )
            SELECT
                `moves_blob`,
                `eventID`,
                `siteID`,
                `Year`,
                `Month`,
                `Day`,
                `Round`,
                `WhiteID`,
                `BlackID`,
                `Result`,
                `WhiteElo`,
                `BlackElo`,
                `ecoID`
            FROM `{IMPORT_TABLE}`
            """
        )

    curs.execute(f"TRUNCATE TABLE `{IMPORT_TABLE}`")

    mydb.close()

    shutil.rmtree(PGN_DIR, ignore_errors=True)
    shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)

    decode_data.decode_events()
    decode_data.decode_sites()
    decode_data.decode_players()

    removeDuplicates.main("all")
    removeSimilar.main("all")

    if args.poland:
        removeDuplicates.main("poland")
        removeSimilar.main("poland")
