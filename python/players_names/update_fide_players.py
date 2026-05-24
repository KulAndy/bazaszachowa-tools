#!/usr/local/bin/python3

import os
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import mysql.connector

from settings import SETTINGS


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
    cursor.execute("""TRUNCATE TABLE `fide_players` """)

    query = (
            "INSERT INTO fide_players "
            "(fideid, name, country, sex, title, w_title, o_title, "
            "rating, rapid_rating, "
            "blitz_rating, birthday) "
            "VALUES (" + ",".join(["%s"] * 11) +
            ") "
            "ON DUPLICATE KEY UPDATE "
            "title = VALUES(title), w_title = VALUES(w_title), o_title = VALUES(o_title), "
            "rating = VALUES(rating), "
            "rapid_rating = VALUES(rapid_rating), "
            "blitz_rating = VALUES(blitz_rating), "
            "birthday = VALUES(birthday)"
    )

    for player in root.findall("player"):
        fideid = player.find("fideid").text
        name = player.find("name").text
        country = player.find("country").text
        sex = player.find("sex").text
        title = player.find("title").text
        w_title = player.find("w_title").text
        o_title = player.find("o_title").text
        rating = player.find("rating").text
        rapid_rating = player.find("rapid_rating").text
        blitz_rating = player.find("blitz_rating").text
        birthday = player.find("birthday").text

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

    try:
        os.remove("players_list_xml.xml")
    except OSError as e:
        pass


def main():
    extract_list("http://ratings.fide.com/download/players_list_xml_legacy.zip")
    import_list("players_list_xml.xml")


if __name__ == "__main__":
    main()
