from urllib.parse import quote_plus

import mysql.connector
from pymongo import MongoClient
from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS["mysql"]
)

MONGO_URI = (
    f"mongodb://{quote_plus(SETTINGS['mongo']['user'])}:"
    f"{quote_plus(SETTINGS['mongo']['password'])}@"
    f"{SETTINGS['mongo']['host']}:27017/{SETTINGS['mongo']['database']}"
)
MONGO_COLLECTION = "poland_tournaments"
mongo = MongoClient(MONGO_URI)

mdb = mongo[SETTINGS['mongo']['database']]
coll = mdb[MONGO_COLLECTION]

if __name__ == "__main__":
    curs = mydb.cursor()
    curs.execute("""SELECT p1.id, p2.id
FROM `subtitutions` 
INNER JOIN players as p1
ON p1.fullname = subtitutions.fullname
INNER JOIN players as p2
ON p2.fullname = subtitutions.substitute
""")
    rows = curs.fetchall()
    for row in rows:
        fullname_id, substitue_id = row
        coll.update_many(
            {"players": substitue_id},
            {"$addToSet": {"players": fullname_id}}
        )

        coll.update_many(
            {"players": substitue_id},
            {"$pull": {"players": substitue_id}}
        )
