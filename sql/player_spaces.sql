DELIMITER $$
CREATE PROCEDURE `player_spaces`()
    SQL SECURITY INVOKER
BEGIN
    UPDATE IGNORE players
    SET fullname = TRIM(fullname);

    UPDATE all_games as g
    INNER JOIN `all_players` as p1
        ON g.WhiteID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, "\\s+$", "") = p2.fullname
    SET g.WhiteID = p2.id
    WHERE p1.`fullname` REGEXP '\\s+$';

    UPDATE poland_games as g
    INNER JOIN `poland_players` as p1
        ON g.WhiteID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, "\\s+$", "") = p2.fullname
    SET g.WhiteID = p2.id
    WHERE p1.`fullname` REGEXP '\\s+$';

    UPDATE all_games as g
    INNER JOIN `all_players` as p1
        ON g.WhiteID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, ",\\s*", ", ") = p2.fullname
    SET g.WhiteID = p2.id
    WHERE p1.`fullname` REGEXP ',\\w';

    UPDATE poland_games as g
    INNER JOIN `poland_players` as p1
        ON g.WhiteID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, ",\\s*", ", ") = p2.fullname
    SET g.WhiteID = p2.id
    WHERE p1.`fullname` REGEXP ',\\w';

    UPDATE all_games as g
    INNER JOIN `all_players` as p1
        ON g.BlackID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, ",\\s*", ", ") = p2.fullname
    SET g.BlackID = p2.id
    WHERE p1.`fullname` REGEXP ',\\w';

    UPDATE poland_games as g
    INNER JOIN `poland_players` as p1
        ON g.BlackID = p1.id
    INNER JOIN players as p2
        ON REGEXP_REPLACE(p1.fullname, ",\\s*", ", ") = p2.fullname
    SET g.BlackID = p2.id
    WHERE p1.`fullname` REGEXP ',\\w';

END$$
DELIMITER ;