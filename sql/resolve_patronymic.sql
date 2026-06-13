DELIMITER $$
CREATE PROCEDURE `resolve_patronymic`()
BEGIN
    INSERT IGNORE INTO subtitutions(fullname, substitute)
    SELECT DISTINCT players.fullname, all_players.fullname
    FROM all_players
    INNER JOIN players
        ON players.fullname = REGEXP_REPLACE(all_players.fullname, "[\\s,]+[\\w']+$", "")
        AND players.fullname != all_players.fullname
    WHERE all_players.fullname REGEXP "\\w+(ovich|evich|ovna|yevna|ichna)$"
        AND all_players.fullname LIKE "% % %";

    INSERT IGNORE INTO subtitutions(fullname, substitute)
    SELECT DISTINCT fide_players.name, all_players.fullname
    FROM all_players
    INNER JOIN fide_players
        ON fide_players.name = REGEXP_REPLACE(all_players.fullname, "[\\s,]+[\\w']+$", "")
        AND fide_players.name != all_players.fullname
    WHERE all_players.fullname REGEXP "\\w+(ovich|evich|ovna|yevna|ichna)$"
        AND all_players.fullname LIKE "% % %";


    INSERT IGNORE INTO subtitutions(fullname, substitute)
    SELECT DISTINCT players.fullname, poland_players.fullname
    FROM poland_players
    INNER JOIN players
        ON players.fullname = REGEXP_REPLACE(poland_players.fullname, "[\\s,]+[\\w']+$", "")
        AND players.fullname != poland_players.fullname
    WHERE poland_players.fullname REGEXP "\\w+(ovich|evich|ovna|yevna|ichna)$"
        AND poland_players.fullname LIKE "% % %";


    INSERT IGNORE INTO subtitutions(fullname, substitute)
    SELECT DISTINCT fide_players.name, poland_players.fullname
    FROM poland_players
    INNER JOIN fide_players
        ON fide_players.name = REGEXP_REPLACE(poland_players.fullname, "[\\s,]+[\\w']+$", "")
        AND fide_players.name != poland_players.fullname
    WHERE poland_players.fullname REGEXP "\\w+(ovich|evich|ovna|yevna|ichna)$"
        AND poland_players.fullname LIKE "% % %";

    UPDATE IGNORE `subtitutions`
    JOIN fide_players
        ON REPLACE(subtitutions.fullname, "'", "") = fide_players.name
    SET subtitutions.fullname = fide_players.name
    WHERE subtitutions.fullname LIKE "%'%";

    DELETE `subtitutions`
    FROM `subtitutions`
    JOIN fide_players
        ON REPLACE(subtitutions.fullname, "'", "") = fide_players.name
    WHERE subtitutions.fullname LIKE "%'%";

END$$
DELIMITER ;