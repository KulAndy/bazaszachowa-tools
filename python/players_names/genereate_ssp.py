import json

import mysql.connector
from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS["mysql"]
)

curs = mydb.cursor()

sql = """SELECT fullname, fide_players.fideid, JSON_ARRAYAGG(substitute)
FROM `subtitutions`
LEFT JOIN fide_players
ON subtitutions.fullname = fide_players.name
GROUP BY fullname """

curs.execute(sql)
with open("my_spell.ssp", 'w') as file:
    file.write('@PLAYER "., -_*"\n')
    while row := curs.fetchone():
        fullname, fide_id, substitutions_string = row
        substitutions = json.loads(substitutions_string)
        file.write(f"{fullname}\n")
        if fide_id:
            file.write(f"   %Bio FIDEID {fide_id}\n")

        for substitute in substitutions:
            file.write(f"   = {substitute}\n")
