#!/usr/local/bin/python3

import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime

import mysql.connector
from settings import SETTINGS


def get_month_year_list(start_date_str):
    start_date = datetime.strptime(start_date_str, '%d-%m-%Y')
    current_date = datetime.now()

    month_year_list = []

    while start_date <= current_date:
        month_name = start_date.strftime('%B')
        year = start_date.strftime('%y')
        month_year_list.append([month_name, year])

        if start_date.month == 12:
            start_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            start_date = start_date.replace(month=start_date.month + 1)

    return month_year_list


def extract_list(url):
    file_name, headers = urllib.request.urlretrieve(url)
    with zipfile.ZipFile(file_name, "r") as zip_ref:
        zip_ref.extractall()


def import_list(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    cnx = mysql.connector.connect(
        **SETTINGS['mysql']
    )
    cursor = cnx.cursor()

    cnx.start_transaction()

    players_query = (
            "INSERT IGNORE INTO fide_players "
            "(fideid, name, country, sex, title, w_title, o_title, "
            "rating, rapid_rating, "
            "blitz_rating, birthday) "
            "VALUES (" + ",".join(["%s"] * 11) +
            ") "
    )

    border_query = (
        "INSERT INTO fide_borders "
        "(`fideid`, `max_rating`, `min_rating`) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "max_rating = GREATEST(max_rating, VALUES(max_rating)), "
        "min_rating = LEAST(min_rating, VALUES(min_rating)) "
    )

    player_params = []
    border_params = []

    for player in root.findall("player"):
        fideid = player.find("fideid").text
        name = player.find("name").text
        country = player.find("country").text
        sex = player.find("sex").text
        title = player.find("title").text
        w_title = player.find("w_title").text
        o_title = player.find("o_title").text
        birthday = player.find("birthday").text

        rating = player.find("rating").text

        try:
            rating_int = int(rating)
        except ValueError:
            rating_int = 0

        try:
            rapid_rating = player.find("rapid_rating").text
            rapid_rating_int = int(rapid_rating)
        except (ValueError, AttributeError):
            rapid_rating = None
            rapid_rating_int = None

        try:
            blitz_rating = player.find("blitz_rating").text
            blitz_rating_int = int(blitz_rating)
        except (ValueError, AttributeError):
            blitz_rating = None
            blitz_rating_int = None

        ratings = [x
                   for x in
                   [rating_int, rapid_rating_int, blitz_rating_int]
                   if x is not None
                   ]
        min_rating = min(ratings)
        max_rating = max(ratings)

        if max_rating == 0:
            continue

        # Only include the values for the INSERT part in the data tuple
        player_data = (
            fideid,
            name,
            country,
            sex,
            title,
            w_title,
            o_title,
            rating,
            rapid_rating,
            blitz_rating,
            birthday,
        )

        border_data = (
            fideid,
            max_rating,
            min_rating
        )

        border_params.append(border_data)
        player_params.append(player_data)

        if len(border_params) % 1000 == 0:
            cursor.executemany(players_query, player_params)
            cursor.executemany(border_query, border_params)

    if border_params:
        cursor.executemany(players_query, player_params)
        cursor.executemany(border_query, border_params)

    cnx.commit()

    cursor.close()
    cnx.close()

    try:
        os.remove(filename)
    except OSError:
        pass


def xml_addr(month_name, year_short):
    return [
        f"http://ratings.fide.com/download/standard_{month_name[:3].lower()}{year_short}frl_xml.zip",
        f"standard_{month_name[:3].lower()}{year_short}frl_xml.xml",
    ]


def main():
    # date_string = get_month_year_list("01-08-2012")
    date_string = get_month_year_list("01-03-2026")
    remote_xml_files = [xml_addr(*i) for i in date_string]
    for remote_data in remote_xml_files:
        print(remote_data)
        extract_list(remote_data[0])
        import_list(remote_data[1])


if __name__ == "__main__":
    main()
