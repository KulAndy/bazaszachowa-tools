import os
from datetime import datetime
from zipfile import ZipFile

import requests

from . import DOWNLOAD_DIR, PGN_DIR

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PGN_DIR, exist_ok=True)

def calculate_date_difference(start_date, end_date):
    return (end_date - start_date).days


def download_file(url, dest_path):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, stream=True)

    if response.status_code != 200:
        return False

    with open(dest_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    return True


def unzip_file(zip_path, extract_dir):
    try:
        with ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
    except Exception as e:
        print(f"Failed to unzip {zip_path}: {e}")


def scrap_twic():
    start_date = datetime(2012, 6, 25).date()
    current_date = datetime.now().date()

    total_days = calculate_date_difference(start_date, current_date)
    total_weeks = total_days // 7

    latest_issue = 920 + total_weeks

    zip_filename = f"twic{latest_issue}g.zip"
    zip_url = f"https://theweekinchess.com/zips/{zip_filename}"
    zip_path = DOWNLOAD_DIR / zip_filename

    if download_file(zip_url, zip_path):
        unzip_file(zip_path, PGN_DIR)

if __name__ == "__main__":
    scrap_twic()
