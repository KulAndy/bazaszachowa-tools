DELIMITER $$
CREATE PROCEDURE `clean_all`()
    SQL SECURITY INVOKER
BEGIN

    DELETE FROM all_games WHERE LENGTH(moves_blob) <= 12;

    DELETE all_games FROM all_games
    INNER JOIN players as p1
        on WhiteID = p1.id
    INNER JOIN players as p2
        on BlackID = p2.id
    WHERE p1.fullname = "N, N" AND p2.fullname = "N, N";

    DELETE t1
    FROM `all_games` as t1
    INNER JOIN `all_games` as t2
        USING(Result, Year, ecoID, BlackID, moves_blob)
    INNER JOIN all_players
        ON t1.WhiteID = all_players.id
    WHERE t1.WhiteID != t2.WhiteID AND all_players.fullname = "N, N";

    DELETE t1
    FROM `all_games` as t1
    INNER JOIN `all_games` as t2
        USING(Result, Year, ecoID, WhiteID, moves_blob)
    INNER JOIN all_players
        ON t1.BlackID = all_players.id
    WHERE t1.BlackID != t2.BlackID AND all_players.fullname = "N, N";

    DELETE `all_games`
    FROM `all_games`
    JOIN sites
        ON siteID = sites.id
    WHERE site REGEXP "^https://lichess.org/\\w+$";

END$$
DELIMITER ;

