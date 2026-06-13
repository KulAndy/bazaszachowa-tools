DELIMITER $$
CREATE PROCEDURE `correct_priest`()
    SQL SECURITY INVOKER
BEGIN
    UPDATE `poland_games` as games
    INNER JOIN `poland_players` as players
        ON games.WhiteID = players.id
    INNER JOIN `poland_players` as players2
        ON SUBSTRING(players.fullname, 4) = players2.fullname
    SET games.WhiteID = players2.id
    WHERE players.fullname LIKE 'ks %';

    UPDATE `poland_games` as games
    INNER JOIN `poland_players` as players
        ON games.BlackID = players.id
    INNER JOIN `poland_players` as players2
        ON SUBSTRING(players.fullname, 4) = players2.fullname
    SET games.BlackID = players2.id
    WHERE players.fullname LIKE 'ks %';

    UPDATE `all_games` as games
    INNER JOIN `all_players` as players
        ON games.WhiteID = players.id
    INNER JOIN `all_players` as players2
        ON SUBSTRING(players.fullname, 4) = players2.fullname
    SET games.WhiteID = players2.id
    WHERE players.fullname LIKE 'ks %';

    UPDATE `all_games` as games
    INNER JOIN `all_players` as players
        ON games.BlackID = players.id
    INNER JOIN `all_players` as players2
        ON SUBSTRING(players.fullname, 4) = players2.fullname
    SET games.BlackID = players2.id
    WHERE players.fullname LIKE 'ks %';

END$$
DELIMITER ;

