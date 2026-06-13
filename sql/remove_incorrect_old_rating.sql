DELIMITER $$
CREATE PROCEDURE `remove_incorrect_old_rating`()
BEGIN
    SELECT @MIN_YEAR := 2007, @MAX_YEAR := 2012, @MAX_DIFF := 400;

    UPDATE
    all_games as a
    JOIN
    (
        SELECT MAX(WhiteElo) as elo, WhiteID
        FROM `all_games`
        WHERE Year = 2013
        AND Month IS NOT null
        GROUP BY WhiteID
    ) as pom
    USING(WhiteID)
    SET a.WhiteElo = null
    WHERE a.Year BETWEEN @MIN_YEAR AND @MAX_YEAR
    AND a.WhiteElo > pom.elo + @MAX_DIFF;


    UPDATE
    all_games as a
    JOIN
    (
        SELECT MAX(BlackElo) as elo, BlackID
        FROM `all_games`
        WHERE Year = 2013
        AND Month IS NOT null
        GROUP BY BlackID
    ) as pom
    USING(BlackID)
    SET a.BlackElo = null
    WHERE a.Year BETWEEN @MIN_YEAR AND @MAX_YEAR
    AND a.BlackElo > pom.elo + @MAX_DIFF;

END$$
DELIMITER ;

