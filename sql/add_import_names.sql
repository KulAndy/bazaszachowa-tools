DELIMITER $$
CREATE PROCEDURE `add_import_names`()
    SQL SECURITY INVOKER
BEGIN
    INSERT IGNORE INTO players(fullname)
    SELECT DISTINCT white as player FROM `import_all`;

    INSERT IGNORE INTO players(fullname)
    SELECT DISTINCT Black as player FROM `import_all`;

    INSERT IGNORE INTO sites(Site)
    SELECT DISTINCT Site FROM `import_all`;

    INSERT IGNORE INTO chess_events(name)
    SELECT DISTINCT Event FROM `import_all` ;

    INSERT IGNORE INTO players(fullname)
    SELECT DISTINCT white as player FROM `import_pol`;

    INSERT IGNORE INTO players(fullname)
    SELECT DISTINCT Black as player FROM `import_pol`;

    INSERT IGNORE INTO sites(Site)
    SELECT DISTINCT Site FROM `import_pol`;

    INSERT IGNORE INTO chess_events(name)
    SELECT DISTINCT Event FROM `import_pol` ;

END$$
DELIMITER ;

