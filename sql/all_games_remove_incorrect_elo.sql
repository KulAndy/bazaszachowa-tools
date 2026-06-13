DELIMITER $$
CREATE PROCEDURE `all_games_remove_incorrect_elo`()
BEGIN
    -- 1. Create temporary table
    CREATE TEMPORARY TABLE tmp_fide_rating_ranges AS
    SELECT
        fp.name,
        MIN(fb.min_rating) AS min_rating,
        MAX(fb.max_rating) AS max_rating
    FROM fide_players fp
    JOIN fide_borders fb
        ON fp.fideid = fb.fideid
    GROUP BY fp.name;

    -- 2. Add index
    ALTER TABLE tmp_fide_rating_ranges
    ADD PRIMARY KEY (name);

    -- 3. Main query
    UPDATE all_games g
    JOIN all_players p
        ON g.WhiteID = p.id
    JOIN tmp_fide_rating_ranges t
        ON p.fullname = t.name
    SET WhiteElo = null
    WHERE
        g.WhiteElo IS NOT NULL
        AND g.Year >= 2001
        AND g.Month IS NOT NULL
        AND NOT ( g.WhiteElo BETWEEN t.min_rating  AND t.max_rating );

    UPDATE all_games g
    JOIN all_players p
        ON g.BlackID = p.id
    JOIN tmp_fide_rating_ranges t
        ON p.fullname = t.name
    SET BlackElo = null
    WHERE
        g.BlackElo IS NOT NULL
        AND g.Year >= 2001
        AND g.Month IS NOT NULL
        AND NOT ( g.BlackElo BETWEEN t.min_rating  AND t.max_rating );
    DROP TEMPORARY TABLE tmp_fide_rating_ranges;

END$$
DELIMITER ;

