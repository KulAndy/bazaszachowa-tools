DELIMITER $$
CREATE PROCEDURE `switch_names_all`()
    SQL SECURITY INVOKER
BEGIN
    UPDATE IGNORE players
    SET fullname = trim(
        concat(
            SUBSTRING_INDEX(SUBSTRING_INDEX(fullname, ',', 2), ',', -1),
            ', ',
            SUBSTRING_INDEX(fullname, ',', 1))
        )
    WHERE `fullname` REGEXP '^\\w,.{5,}'  ;

    UPDATE `all_games`
    INNER JOIN `all_players` as t1
        on all_games.WhiteID = t1.id
    INNER JOIN players as t2
        ON trim(
                concat(
                    SUBSTRING_INDEX(SUBSTRING_INDEX(t1.fullname, ',', 2), ',', -1),
                    ', '
                    , SUBSTRING_INDEX(t1.fullname, ',', 1)
                    )
            ) = t2.fullname
    SET
    WhiteID = t2.id
    WHERE t1.`fullname` REGEXP '^\\w,{5,}';

    UPDATE `all_games`
    INNER JOIN `all_players` as t1
        on all_games.BlackID = t1.id
    INNER JOIN players as t2
        ON trim(
            concat(SUBSTRING_INDEX(SUBSTRING_INDEX(t1.fullname, ',', 2), ',', -1),
            ', '
            , SUBSTRING_INDEX(t1.fullname, ',', 1))
            ) = t2.fullname
    SET
    BlackID = t2.id
    WHERE t1.`fullname` REGEXP '^\\w,.{5,}';
END$$
DELIMITER ;
