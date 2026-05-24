import re
import mysql.connector

from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS['mysql']
)
mydb.autocommit = True
curs = mydb.cursor()


def process_substitutions(player, substitutions):
    if player and substitutions:
        print(player)
        params = [
            (player, x)
            for x in substitutions
        ]
        curs.executemany("""INSERT IGNORE INTO `subtitutions`(`fullname`, `substitute`) 
        VALUES (%s, %s) """, params)


def main():
    with open("ratings0425.ssp", 'r') as file:
        player_data = False
        player = ""
        substitutions = []
        for line in file:
            line = line.strip()
            line = re.sub("#.*", "", line)

            if line.startswith("@"):
                if line.startswith("@PLAYER"):
                    player_data = True
                else:
                    player_data = False

            if not player_data or line.startswith("%"):
                continue
            if line.startswith("="):
                substitutions.append(
                                    line
                                        .replace("=", "")
                                        .strip()
                                     )
            else:
                process_substitutions(player, substitutions)
                player = line
                substitutions = []

        process_substitutions(player, substitutions)

if __name__ == "__main__":
    main()