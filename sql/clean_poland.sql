DELIMITER $$
CREATE PROCEDURE `clean_poland`()
    SQL SECURITY INVOKER
BEGIN
    DELETE FROM poland_games WHERE LENGTH(moves_blob) <= 12;

    DELETE poland_games FROM poland_games
    INNER JOIN players as p1
        on WhiteID = p1.id
    INNER JOIN players as p2
        on BlackID = p2.id
    WHERE p1.fullname = "N, N" AND p2.fullname = "N, N";

    DELETE t1
    FROM `poland_games` as t1
    INNER JOIN `poland_games` as t2
        USING(ecoID, BlackID, moves_blob, Year)
    INNER JOIN poland_players
        ON t1.WhiteID = poland_players.id
    WHERE t1.WhiteID != t2.WhiteID AND poland_players.fullname = "N, N";

    DELETE t1
    FROM `poland_games` as t1
    INNER JOIN `poland_games` as t2
        USING(ecoID, WhiteID, moves_blob, Year)
    INNER JOIN poland_players
        ON t1.BlackID = poland_players.id
    WHERE t1.BlackID != t2.BlackID AND poland_players.fullname = "N, N";

    DELETE `poland_games`
    FROM `poland_games`
    JOIN sites
        ON siteID = sites.id
    WHERE site REGEXP "^https://lichess.org/\\w+$";

END$$
DELIMITER ;
