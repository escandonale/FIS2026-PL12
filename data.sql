UPDATE offer
SET registrations_open = 1,
    member_registration_start = date('now'),
    member_registration_end = date('now', '+5 days'),
    non_member_registration_start = date('now', '+6 days'),
    non_member_registration_end = date('now', '+11 days'),
    member_registration_status = 'open',
    non_member_registration_status = 'open'
WHERE id = 1;

INSERT INTO activity (
    id, category, level, installation_id, start_date, start_time, end_time,
    available_places, occupied_places, member_registration_start,
    member_registration_end, non_member_registration_start,
    non_member_registration_end
) VALUES
    (1, 'Pilates', 'Medio',
        (SELECT id FROM installation WHERE name = 'Gimnasio'),
        date('now', '+90 days'), '09:00', '10:00', 30, 30,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (2, 'Pilates', 'Iniciación',
        (SELECT id FROM installation WHERE name = 'Sala de Actividades 1'),
        date('now', '+91 days'), '10:00', '11:00', 30, 15,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (3, 'Acondicionamiento Físico', 'Medio',
        (SELECT id FROM installation WHERE name = 'Sala de Actividades 2'),
        date('now', '+92 days'), '11:00', '12:00', 30, 18,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (4, 'Natación', 'Iniciación',
        (SELECT id FROM installation WHERE name = 'Piscina Pequeña'),
        date('now', '+93 days'), '12:00', '13:00', 30, 21,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (5, 'Padel', 'Avanzado',
        (SELECT id FROM installation WHERE name = 'Pista de Pádel 1'),
        date('now', '+94 days'), '13:00', '14:00', 30, 24,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (6, 'Tenis', 'Medio',
        (SELECT id FROM installation WHERE name = 'Pista de Ténis 1'),
        date('now', '+95 days'), '14:00', '15:00', 30, 27,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (7, 'Natación', 'Avanzado',
        (SELECT id FROM installation WHERE name = 'Piscina Grande'),
        date('now', '+96 days'), '15:00', '16:00', 30, 15,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (8, 'Pilates', 'Avanzado',
        (SELECT id FROM installation WHERE name = 'Sala de Actividades 3'),
        date('now', '+97 days'), '16:00', '17:00', 30, 18,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (9, 'Acondicionamiento Físico', 'Iniciación',
        (SELECT id FROM installation WHERE name = 'Gimnasio'),
        date('now', '+98 days'), '17:00', '18:00', 30, 21,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days')),
    (10, 'Padel', 'Medio',
        (SELECT id FROM installation WHERE name = 'Pista de Pádel 2'),
        date('now', '+99 days'), '18:00', '19:00', 30, 24,
        date('now'), date('now', '+5 days'),
        date('now', '+6 days'), date('now', '+11 days'));

INSERT INTO activity_day (activity_id, weekday) VALUES
    (1, 'Lunes'),
    (2, 'Martes'),
    (3, 'Miércoles'),
    (4, 'Jueves'),
    (5, 'Viernes'),
    (6, 'Sábado'),
    (7, 'Domingo'),
    (8, 'Lunes'),
    (9, 'Martes'),
    (10, 'Miércoles');

WITH RECURSIVE numbers(value) AS (
    SELECT 1
    UNION ALL
    SELECT value + 1 FROM numbers WHERE value < 71
)
INSERT INTO Socios (nombre, apellidos, dni, numero_socio, direccion, genero)
SELECT
    'Socio' || printf('%03d', value),
    'Usuario de prueba',
    'SOCIO-' || printf('%03d', value),
    'N-' || printf('%03d', value),
    'Calle de prueba ' || value,
    CASE value % 3 WHEN 0 THEN 'm' WHEN 1 THEN 'f' ELSE 'n' END
FROM numbers;

WITH RECURSIVE numbers(value) AS (
    SELECT 1
    UNION ALL
    SELECT value + 1 FROM numbers WHERE value < 142
)
INSERT INTO no_socio (
    nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo
)
SELECT
    'NoSocio' || printf('%03d', value),
    'Usuario de prueba',
    date('now', '-' || (18 + value % 40) || ' years'),
    CASE value % 3 WHEN 0 THEN 'm' WHEN 1 THEN 'f' ELSE 'n' END,
    'Avenida de prueba ' || value,
    'NO-SOCIO-' || printf('%03d', value),
    'no-socio' || value || '@example.test'
FROM numbers;

WITH RECURSIVE
enrollment_counts(activity_id, member_count, non_member_count) AS (
    VALUES
        (1, 10, 20),
        (2, 5, 10),
        (3, 6, 12),
        (4, 7, 14),
        (5, 8, 16),
        (6, 9, 18),
        (7, 5, 10),
        (8, 6, 12),
        (9, 7, 14),
        (10, 8, 16)
),
member_offsets AS (
    SELECT
        activity_id,
        member_count,
        COALESCE(
            SUM(member_count) OVER (
                ORDER BY activity_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        ) AS user_offset
    FROM enrollment_counts
),
member_rows(activity_id, member_count, user_offset, position) AS (
    SELECT activity_id, member_count, user_offset, 1 FROM member_offsets
    UNION ALL
    SELECT activity_id, member_count, user_offset, position + 1
    FROM member_rows
    WHERE position < member_count
)
INSERT INTO inscripcion (
    activity_id, nombre, apellidos, dni, estado, fecha_inscripcion, es_socio
)
SELECT
    activity_id,
    'Socio' || printf('%03d', user_offset + position),
    'Usuario de prueba',
    'SOCIO-' || printf('%03d', user_offset + position),
    'confirmado',
    datetime('now'),
    1
FROM member_rows
ORDER BY activity_id, position;

WITH RECURSIVE
enrollment_counts(activity_id, member_count, non_member_count) AS (
    VALUES
        (1, 10, 20),
        (2, 5, 10),
        (3, 6, 12),
        (4, 7, 14),
        (5, 8, 16),
        (6, 9, 18),
        (7, 5, 10),
        (8, 6, 12),
        (9, 7, 14),
        (10, 8, 16)
),
non_member_offsets AS (
    SELECT
        activity_id,
        non_member_count,
        COALESCE(
            SUM(non_member_count) OVER (
                ORDER BY activity_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        ) AS user_offset
    FROM enrollment_counts
),
non_member_rows(activity_id, non_member_count, user_offset, position) AS (
    SELECT activity_id, non_member_count, user_offset, 1
    FROM non_member_offsets
    UNION ALL
    SELECT activity_id, non_member_count, user_offset, position + 1
    FROM non_member_rows
    WHERE position < non_member_count
)
INSERT INTO inscripcion (
    activity_id, nombre, apellidos, dni, estado, fecha_inscripcion, es_socio
)
SELECT
    activity_id,
    'NoSocio' || printf('%03d', user_offset + position),
    'Usuario de prueba',
    'NO-SOCIO-' || printf('%03d', user_offset + position),
    'confirmado',
    datetime('now'),
    0
FROM non_member_rows
ORDER BY activity_id, position;
