import os
from pathlib import Path

from ..chess_scrappers.chessresults_scrapper2 import main as scrap
from . import PGN_DIR

os.makedirs(PGN_DIR, exist_ok=True)


def scrap_chessresult() -> None:
    scrap(False)
    Path("chessresults.pgn").rename(PGN_DIR / "chessresults.pgn")


if __name__ == "__main__":
    scrap_chessresult()
