DELIMITER $$
CREATE PROCEDURE `correct_asian_lichess`()
BEGIN
    INSERT IGNORE INTO sites(site)
    SELECT DISTINCT
        SUBSTRING_INDEX(site, '/', LENGTH(site) - LENGTH(REPLACE(site,'/',''))) AS url_up_to_last
    FROM
        sites
    WHERE
        site REGEXP "https://lichess.org/broadcast/202\\d-*[a-z]?/round-\\d+/.*/.*";

    UPDATE `all_games`
    JOIN sites as s1
        on siteID = s1.id
    JOIN sites as s2
        on s2.site = SUBSTRING_INDEX(s1.site, '/', LENGTH(s1.site) - LENGTH(REPLACE(s1.site,'/','')))
    SET siteID = s2.id
    WHERE s1.site REGEXP "https://lichess.org/broadcast/202\\d-*[a-z]?/round-\\d+/.*/.*";

    DELETE FROM sites
    WHERE site REGEXP "https://lichess.org/broadcast/202\\d-*[a-z]?/round-\\d+/.*/.*";

END$$
DELIMITER ;

