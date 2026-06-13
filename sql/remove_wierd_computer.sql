DELIMITER $$
CREATE PROCEDURE `remove_wierd_computer`()
    DELETE all_games
    FROM `all_games`
    INNER JOIN wierd_all_players as p1
        ON p1.id = WhiteID
    INNER JOIN wierd_all_players as p2
        ON p2.id = BlackID
    WHERE p1.fullname NOT LIKE "% %" AND p2.fullname NOT LIKE "% %"$$

DELIMITER ;

