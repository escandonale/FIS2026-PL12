DROP TRIGGER IF EXISTS prevent_activity_schedule_conflict_on_assignment;
DROP TRIGGER IF EXISTS prevent_activity_schedule_conflict_on_day_insert;
DROP TRIGGER IF EXISTS prevent_activity_schedule_conflict_on_day_update;
DROP TRIGGER IF EXISTS prevent_activity_schedule_conflict_on_time_update;
DROP TRIGGER IF EXISTS prevent_activity_schedule_conflict_on_activity_insert;
DROP TRIGGER IF EXISTS validate_activity_times_on_insert;
DROP TRIGGER IF EXISTS validate_activity_times_on_update;

CREATE TRIGGER validate_activity_times_on_insert
BEFORE INSERT ON activity
WHEN NOT (
    NEW.start_time IS NOT NULL
    AND NEW.end_time IS NOT NULL
    AND (
        NEW.start_time GLOB '[01][0-9]:[0-5][0-9]'
        OR NEW.start_time GLOB '2[0-3]:[0-5][0-9]'
    )
    AND (
        NEW.end_time GLOB '[01][0-9]:[0-5][0-9]'
        OR NEW.end_time GLOB '2[0-3]:[0-5][0-9]'
    )
    AND NEW.end_time > NEW.start_time
)
BEGIN
    SELECT RAISE(ABORT, 'invalid_activity_time');
END;

CREATE TRIGGER validate_activity_times_on_update
BEFORE UPDATE OF start_time, end_time ON activity
WHEN NOT (
    NEW.start_time IS NOT NULL
    AND NEW.end_time IS NOT NULL
    AND (
        NEW.start_time GLOB '[01][0-9]:[0-5][0-9]'
        OR NEW.start_time GLOB '2[0-3]:[0-5][0-9]'
    )
    AND (
        NEW.end_time GLOB '[01][0-9]:[0-5][0-9]'
        OR NEW.end_time GLOB '2[0-3]:[0-5][0-9]'
    )
    AND NEW.end_time > NEW.start_time
)
BEGIN
    SELECT RAISE(ABORT, 'invalid_activity_time');
END;

CREATE TRIGGER IF NOT EXISTS prevent_activity_schedule_conflict_on_assignment
BEFORE UPDATE OF installation_id ON activity
WHEN NEW.installation_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'schedule_conflict')
    WHERE EXISTS (
        SELECT 1
        FROM activity_day AS current_day
        JOIN activity AS other
            ON other.installation_id = NEW.installation_id
            AND other.id != NEW.id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = current_day.weekday
        WHERE current_day.activity_id = NEW.id
          AND other.start_time < NEW.end_time
          AND other.end_time > NEW.start_time
    );
END;

CREATE TRIGGER prevent_activity_schedule_conflict_on_activity_insert
BEFORE INSERT ON activity
WHEN NEW.installation_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'schedule_conflict')
    WHERE EXISTS (
        SELECT 1
        FROM activity_day AS new_day
        JOIN activity AS other
            ON other.installation_id = NEW.installation_id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = new_day.weekday
        WHERE new_day.activity_id = NEW.id
          AND other.start_time < NEW.end_time
          AND other.end_time > NEW.start_time
    );
END;

CREATE TRIGGER IF NOT EXISTS prevent_activity_schedule_conflict_on_day_insert
BEFORE INSERT ON activity_day
BEGIN
    SELECT RAISE(ABORT, 'schedule_conflict')
    WHERE EXISTS (
        SELECT 1
        FROM activity AS current
        JOIN activity AS other
            ON other.installation_id = current.installation_id
            AND other.id != current.id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = NEW.weekday
        WHERE current.id = NEW.activity_id
          AND current.installation_id IS NOT NULL
          AND other.start_time < current.end_time
          AND other.end_time > current.start_time
    );
END;

CREATE TRIGGER IF NOT EXISTS prevent_activity_schedule_conflict_on_day_update
BEFORE UPDATE OF activity_id, weekday ON activity_day
BEGIN
    SELECT RAISE(ABORT, 'schedule_conflict')
    WHERE EXISTS (
        SELECT 1
        FROM activity AS current
        JOIN activity AS other
            ON other.installation_id = current.installation_id
            AND other.id != current.id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = NEW.weekday
        WHERE current.id = NEW.activity_id
          AND current.installation_id IS NOT NULL
          AND other.start_time < current.end_time
          AND other.end_time > current.start_time
    );
END;

CREATE TRIGGER IF NOT EXISTS prevent_activity_schedule_conflict_on_time_update
BEFORE UPDATE OF start_time, end_time ON activity
WHEN NEW.installation_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'schedule_conflict')
    WHERE EXISTS (
        SELECT 1
        FROM activity_day AS current_day
        JOIN activity AS other
            ON other.installation_id = NEW.installation_id
            AND other.id != NEW.id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = current_day.weekday
        WHERE current_day.activity_id = NEW.id
          AND other.start_time < NEW.end_time
          AND other.end_time > NEW.start_time
    );
END;
