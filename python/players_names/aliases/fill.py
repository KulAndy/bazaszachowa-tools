import re

import mysql.connector

from ...settings import SETTINGS

mydb = mysql.connector.connect(**SETTINGS["mysql"], autocommit=True)
curs = mydb.cursor()


def process_substitutions(player: str, substitutions: list[str]) -> None:
    if player and substitutions:
        print(player)
        params = [(player, x) for x in substitutions]
        curs.executemany(
            """INSERT IGNORE INTO `subtitutions`(`fullname`, `substitute`) 
        VALUES (%s, %s) """,
            params,
        )


def main() -> None:
    with open("ratings0425.ssp") as file:
        player_data = False
        player = ""
        substitutions = []
        for line in file:
            line = line.strip()
            line = re.sub("#.*", "", line)

            if line.startswith("@"):
                player_data = bool(line.startswith("@PLAYER"))

            if not player_data or line.startswith("%"):
                continue
            if line.startswith("="):
                substitutions.append(line.replace("=", "").strip())
            else:
                process_substitutions(player, substitutions)
                player = line
                substitutions = []

        process_substitutions(player, substitutions)


if __name__ == "__main__":
    main()
