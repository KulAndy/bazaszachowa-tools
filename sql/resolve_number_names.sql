DELIMITER $$
CREATE PROCEDURE `resolve_number_names`()
    SQL SECURITY INVOKER
BEGIN
    INSERT IGNORE INTO players(fullname)
    SELECT REGEXP_REPLACE(fullname, '\\s*\\d+$','')
    FROM poland_players
    WHERE fullname REGEXP '\\s*\\d+$';

    UPDATE poland_players
    INNER JOIN players
        on players.fullname = REGEXP_REPLACE(poland_players.fullname, '\\s*\\d+$','')
    INNER JOIN poland_games
        ON poland_players.id = poland_games.WhiteID
    SET poland_games.WhiteID = players.id
    WHERE poland_players.fullname REGEXP '\\s*\\d+$';

    UPDATE poland_players
    INNER JOIN players
        on players.fullname = REGEXP_REPLACE(poland_players.fullname, '\\s*\\d+$','')
    INNER JOIN poland_games
        ON poland_players.id = poland_games.BlackID
    SET poland_games.BlackID = players.id
    WHERE poland_players.fullname REGEXP '\\s*\\d+$';

    INSERT IGNORE INTO players(fullname)
    SELECT REGEXP_REPLACE(fullname, '\\s*\\d+$','')
    FROM all_players WHERE fullname REGEXP '\\s*\\d+$';

    UPDATE all_players
    INNER JOIN players
        on players.fullname = REGEXP_REPLACE(all_players.fullname, '\\s*\\d+$','')
    INNER JOIN all_games
        ON all_players.id = all_games.WhiteID
    SET all_games.WhiteID = players.id
    WHERE all_players.fullname REGEXP '\\s*\\d+$';

    UPDATE all_players
    INNER JOIN players
        on players.fullname = REGEXP_REPLACE(all_players.fullname, '\\s*\\d+$','')
    INNER JOIN all_games
        ON all_players.id = all_games.BlackID
    SET all_games.BlackID = players.id
    WHERE all_players.fullname REGEXP '\\s*\\d+$';

END$$
DELIMITER ;