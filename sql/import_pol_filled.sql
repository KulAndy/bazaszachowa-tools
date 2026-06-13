DELIMITER $$
CREATE PROCEDURE `import_pol_filled`()
    SQL SECURITY INVOKER
BEGIN
    START TRANSACTION;

    SELECT @max_value := MAX(Year), @min_value := MIN(Year) FROM import_pol;

    DELETE FROM poland_games WHERE Year BETWEEN @min_value AND @max_value;

    INSERT INTO `poland_games`(`moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`, `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID`)
    SELECT `moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`, `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID` FROM import_pol;

    TRUNCATE TABLE import_pol;

    COMMIT;

    UPDATE poland_games
	SET month = null
	WHERE Year = YEAR(CURRENT_DATE) and Month > Month(CURRENT_DATE);

END$$
DELIMITER ;