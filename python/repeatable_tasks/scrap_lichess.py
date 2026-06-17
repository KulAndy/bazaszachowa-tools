import os
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
import zstandard as zstd

from . import DOWNLOAD_DIR, PGN_DIR
from .utils import clean_pgn

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PGN_DIR, exist_ok=True)


def get_latest_broadcast_url():
    today = date.today()

    if today.month == 1:
        year = today.year - 1
        month = 12
    else:
        year = today.year
        month = today.month - 1

    filename = f"lichess_db_broadcast_{year}-{month:02d}.pgn.zst"
    return f"https://database.lichess.org/broadcast/{filename}"


def download_file(url):
    filename = os.path.basename(urlparse(url).path)
    dest_path = os.path.join(DOWNLOAD_DIR, filename)

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    return filename


def decompress_file(filename):
    src_path = Path(DOWNLOAD_DIR) / filename
    output_path = Path(PGN_DIR) / filename.replace(".zst", "")

    with open(src_path, "rb") as compressed:
        dctx = zstd.ZstdDecompressor()

        with open(output_path, "wb") as decompressed:
            dctx.copy_stream(compressed, decompressed)

    clean_pgn(output_path)

def scrap_lichess():
    url = get_latest_broadcast_url()

    filename = download_file(url)
    decompress_file(filename)


if __name__ == "__main__":
    scrap_lichess()