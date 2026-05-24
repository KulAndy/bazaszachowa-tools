import mysql.connector

from settings import SETTINGS

mydb = mysql.connector.connect(
    **SETTINGS['mysql']
)
mydb.autocommit = True
curs = mydb.cursor()

def main():
    sql = """
    DELETE FROM `subtitutions` 
    WHERE substitute IN ("Radzikowska, Krystyna","Hook, Bill","Loyd, Sam", "Pilnik, Hermann", "Planinc, Albin", "Sanguinetti, Raul");
    DELETE s2
    FROM `subtitutions`  as s1
    INNER JOIN subtitutions as s2
    ON s1.fullname = s2.substitute AND s1.substitute = s2.fullname
    INNER JOIN fide_players
    ON s1.fullname = fide_players.name;
    INSERT IGNORE INTO players(fullname)
    SELECT fullname FROM subtitutions;

    INSERT IGNORE INTO players(fullname)
    SELECT `fullname` FROM `subtitutions`;
    CREATE TEMPORARY TABLE tmp_substitutions (
        old_id INT,
        new_id INT
    );
    
    INSERT INTO tmp_substitutions (old_id, new_id)
    SELECT 
        p1.id AS old_id,
        p2.id AS new_id
    FROM players AS p1
    INNER JOIN subtitutions ON p1.fullname = subtitutions.substitute AND p1.fullname != subtitutions.fullname
    INNER JOIN players AS p2 ON p2.fullname = subtitutions.fullname;
    
    UPDATE all_games
    INNER JOIN tmp_substitutions ON all_games.WhiteID = tmp_substitutions.old_id
    SET all_games.WhiteID = tmp_substitutions.new_id;    
    UPDATE all_games
    INNER JOIN tmp_substitutions ON all_games.BlackID = tmp_substitutions.old_id
    SET all_games.BlackID = tmp_substitutions.new_id;
    
    UPDATE poland_games
    INNER JOIN tmp_substitutions ON poland_games.WhiteID = tmp_substitutions.old_id
    SET poland_games.WhiteID = tmp_substitutions.new_id;    
    UPDATE poland_games
    INNER JOIN tmp_substitutions ON poland_games.BlackID = tmp_substitutions.old_id
    SET poland_games.BlackID = tmp_substitutions.new_id;

    UPDATE IGNORE poland_tournament_players as ptp
    INNER JOIN tmp_substitutions ON ptp.player_id = tmp_substitutions.old_id
    SET ptp.player_id = tmp_substitutions.new_id;    

    DELETE ptp 
    FROM poland_tournament_players as ptp
    INNER JOIN tmp_substitutions ON ptp.player_id = tmp_substitutions.old_id;

    DROP TEMPORARY TABLE tmp_substitutions;
    
    DELETE all_players
    FROM all_players 
    INNER JOIN subtitutions
    ON all_players.fullname = subtitutions.substitute;

    DELETE poland_players
    FROM poland_players 
    INNER JOIN subtitutions
    ON poland_players.fullname = subtitutions.substitute
"""
    # sql += """;
    # START TRANSACTION;
    # DELETE FROM all_players;
    # INSERT IGNORE INTO all_players(id, fullname)
    # SELECT pom.id, fullname FROM (SELECT WhiteID as id FROM all_games
    # UNION DISTINCT
    # SELECT BlackID as id FROM all_games) as pom
    # INNER JOIN players
    # on pom.id = players.id;
    # COMMIT
    # """
    # sql += """;
    # START TRANSACTION;
    # DELETE FROM poland_players;
    # INSERT IGNORE INTO poland_players(id, fullname)
    # SELECT pom.id, fullname FROM (SELECT WhiteID as id FROM poland_games
    # UNION DISTINCT
    # SELECT BlackID as id FROM poland_games) as pom
    # INNER JOIN players
    # on pom.id = players.id;
    # COMMIT
    # """
    for query in sql.split(";"):
        curs.execute(query)
if __name__ == "__main__":
    main()