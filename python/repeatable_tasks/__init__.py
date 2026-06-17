from pathlib import Path

HERE = Path(__file__).resolve().parent

DOWNLOAD_DIR = HERE / "downloaded_zips"
PGN_DIR = HERE / "pgns"
CPP_BIN_DIR = HERE.parent.parent / "cpp" / "build"
IMPORT_TABLE = "import_all"
ALL_GAMES_TABLE = "all_games"