#!/usr/local/bin/python3

import contextlib
import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import mysql.connector

from ..settings import SETTINGS


def get_text(player: ET.Element, tag: str) -> str:
    element = player.find(tag)
    if element is None or element.text is None:
        raise ValueError(f"Missing XML field: {tag}")
    return element.text


def extract_list(url: str) -> None:
    file_name, _ = urllib.request.urlretrieve(url)
    with zipfile.ZipFile(file_name, "r") as zip_ref:
        zip_ref.extractall()


def import_list(filename: str) -> None:
    tree = ET.parse(filename)
    root = tree.getroot()

    cnx = mysql.connector.connect(**SETTINGS["mysql"])
    cursor = cnx.cursor()

    cnx.start_transaction()
    cursor.execute("""TRUNCATE TABLE `fide_players` """)

    query = (
        "INSERT INTO fide_players "
        "(fideid, name, country, sex, title, w_title, o_title, "
        "rating, rapid_rating, "
        "blitz_rating, birthday) "
        "VALUES (" + ",".join(["%s"] * 11) + ") "
        "ON DUPLICATE KEY UPDATE "
        "title = VALUES(title), w_title = VALUES(w_title), o_title = VALUES(o_title), "
        "rating = VALUES(rating), "
        "rapid_rating = VALUES(rapid_rating), "
        "blitz_rating = VALUES(blitz_rating), "
        "birthday = VALUES(birthday)"
    )

    for player in root.findall("player"):
        fideid = get_text(player, "fideid")
        name = get_text(player, "name")
        country = get_text(player, "country")
        sex = get_text(player, "sex")
        title = get_text(player, "title")
        w_title = get_text(player, "w_title")
        o_title = get_text(player, "o_title")
        rating = get_text(player, "rating")
        rapid_rating = get_text(player, "rapid_rating")
        blitz_rating = get_text(player, "blitz_rating")
        birthday = get_text(player, "birthday")

        data = (
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
        cursor.execute(query, data)

    cnx.commit()

    cursor.close()
    cnx.close()

    with contextlib.suppress(OSError):
        os.remove("players_list_xml.xml")


def main() -> None:
    extract_list("https://ratings.fide.com/download/players_list_xml_legacy.zip")
    import_list("players_list_xml.xml")


if __name__ == "__main__":
    main()
