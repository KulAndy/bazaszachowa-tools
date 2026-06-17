import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from . import PGN_DIR
from .utils import clean_pgn

os.makedirs(PGN_DIR, exist_ok=True)

def scrap_chessbase():
    url = "https://live.chessbase.com/en/History"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        links = [
            a['href']
            for a in soup.find_all('a', href=True)
            if "Games?" in a['href']
        ]

        pgn_file = Path(PGN_DIR) / "chessbase.pgn"
        with open(pgn_file,'w') as output:
            for link in links:
                tournament_link = f"https://live.chessbase.com{link}"
                parsed_url = urlparse(tournament_link)

                query_params = parse_qs(parsed_url.query)
                pgn_url = f"https://liveserver.chessbase.com:6009/pgn/{query_params['id'][0]}/0/0/all.pgn"
                res = requests.get(pgn_url)
                output.write(res.text)
        clean_pgn(pgn_file)
    else:
        print(f"Failed to fetch the page. Status code: {response.status_code}")


if __name__ == '__main__':
    scrap_chessbase()
