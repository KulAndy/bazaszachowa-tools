DELIMITER $$
CREATE PROCEDURE `import_all_filled`()
    MODIFIES SQL DATA
    SQL SECURITY INVOKER
BEGIN
    DECLARE max_value INT;
    DECLARE min_value INT;

    START TRANSACTION;

    SELECT @max_value := MAX(Year), @min_value := MIN(Year) FROM import_all;

    DELETE FROM all_games WHERE Year BETWEEN @min_value AND @max_value;

    INSERT INTO `all_games`(`moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`, `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID`)
    SELECT `moves_blob`, `eventID`, `siteID`, `Year`, `Month`, `Day`, `Round`, `WhiteID`, `BlackID`, `Result`, `WhiteElo`, `BlackElo`, `ecoID` FROM import_all;

    TRUNCATE TABLE import_all;

    COMMIT;

    UPDATE all_games
	SET month = null
	WHERE Year = YEAR(CURRENT_DATE) and Month > Month(CURRENT_DATE);

END$$
DELIMITER ;

