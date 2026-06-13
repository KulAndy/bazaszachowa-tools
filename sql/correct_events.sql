DELIMITER $$
CREATE PROCEDURE `correct_events`()
BEGIN
    -- part1
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+: \\w+[, ]+\\w+ - \\w+[, ]+\\w+'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+: \\w+[, ]+\\w+ - \\w+[, ]+\\w+'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part2
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ \\| \\d+-\\d+'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ \\| \\d+-\\d+'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part3
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ #'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ #'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part4
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ .*\\d+-day'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ .*\\d+-day'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part5
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ \\(.*(Postponed|board|match|adjourned).*\\)'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+ \\(.*(Postponed|board|match|adjourned).*\\)'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part6
    INSERT IGNORE INTO chess_events(name)
    SELECT DISTINCT REGEXP_SUBSTR( name, '(?<=\\().*?(?=\\))' )
    FROM `chess_events`
    WHERE `name` REGEXP '^Round \\d+ \\(' ORDER BY name;

    UPDATE poland_games g
    JOIN chess_events c1
        ON c1.id = g.eventID
    JOIN chess_events c2
        ON REGEXP_SUBSTR( c1.name, '(?<=\\().*?(?=\\))' ) = c2.name
    SET g.eventID = c2.id
    WHERE c1.name REGEXP '^Round \\d+ \\(';

    UPDATE all_games g
    JOIN chess_events c1
        ON c1.id = g.eventID
    JOIN chess_events c2
        ON REGEXP_SUBSTR( c1.name, '(?<=\\().*?(?=\\))' ) = c2.name
    SET g.eventID = c2.id
    WHERE c1.name REGEXP '^Round \\d+ \\(';

    DELETE IGNORE FROM chess_events;

    -- part7
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+\\W+(\\[Barrage\\]|game\\b|Tiebreak|Postponed)'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+\\W+(\\[Barrage\\]|game\\b|Tiebreak|Postponed)'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part8
    INSERT IGNORE INTO chess_events(name)
    SELECT DISTINCT REGEXP_REPLACE(REGEXP_SUBSTR( name, '(?<=\\d).*?(?=:)' ), "^\\s*[\\|-]?\\s*", "")
    FROM `chess_events`
    WHERE `name` REGEXP '^Round \\d+ [\\|-]?.*?:.*-.*' ORDER BY name;

    UPDATE poland_games g
    JOIN chess_events c1
        ON c1.id = g.eventID
    JOIN chess_events c2
        ON REGEXP_REPLACE(REGEXP_SUBSTR( c1.name, '(?<=\\d).*?(?=:)' ), "^\\s*[\\|-]?\\s*", "") = c2.name
    SET g.eventID = c2.id
    WHERE c1.name REGEXP '^Round \\d+ [\\|-]?.*?:.*-.*';

    UPDATE all_games g
    JOIN chess_events c1
        ON c1.id = g.eventID
    JOIN chess_events c2
        ON REGEXP_REPLACE(REGEXP_SUBSTR( c1.name, '(?<=\\d).*?(?=:)' ), "^\\s*[\\|-]?\\s*", "") = c2.name
    SET g.eventID = c2.id
    WHERE c1.name REGEXP '^Round \\d+ [\\|-]?.*?:.*-.*';

    DELETE IGNORE FROM chess_events;

    -- part9
    UPDATE poland_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+([.-]\\d+)?:.*[\\w+\\).]\\s+(vs|-)\\s+\\w+'
    ) AND c.name = "?";

    UPDATE all_games g, chess_events c
    SET g.eventID = c.id
    WHERE g.eventID IN (
        SELECT id
        FROM `chess_events`
        WHERE `name`
        REGEXP '^Round \\d+([.-]\\d+)?:.*[\\w\\).]\\s+(vs|-)\\s+\\w+'
    ) AND c.name = "?";

    DELETE IGNORE FROM chess_events;

    -- part10
    DELETE
    FROM `poland_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name LIKE "TCEC%"
    );

    DELETE
    FROM `poland_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name REGEXP "^\\d+\\.? TCEC"
    );

    DELETE g
    FROM `all_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name LIKE "TCEC%"
    );

    DELETE g
    FROM `all_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name REGEXP "^\\d+\\.? TCEC"
    );

    DELETE IGNORE FROM chess_events;

    -- part11
    DELETE
    FROM `poland_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name REGEXP '\\bcomp(uter)?s?\\b'
    )
    AND WhiteID IN (
        SELECT id
        FROM poland_players p
        WHERE p.fullname REGEXP '^\\w+$'
    )
    AND BlackID IN (
        SELECT id
        FROM poland_players p
        WHERE p.fullname REGEXP '^\\w+$'
    );

    DELETE g
    FROM `all_games` g
    WHERE eventID IN (
        SELECT id FROM chess_events c
        WHERE c.name REGEXP '\\bcomp(uter)?s?\\b'
    )
    AND WhiteID IN (
        SELECT id
        FROM all_players p
        WHERE p.fullname REGEXP '^\\w+$'
    )
    AND BlackID IN (
        SELECT id
        FROM all_players p
        WHERE p.fullname REGEXP '^\\w+$'
    );

    DELETE IGNORE FROM chess_events;

END$$
DELIMITER ;

