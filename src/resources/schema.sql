CREATE TABLE IF NOT EXISTS offer (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    registrations_open INTEGER NOT NULL DEFAULT 0
        CHECK (registrations_open IN (0, 1))
);

INSERT OR IGNORE INTO offer (id, registrations_open) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS installation (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT OR IGNORE INTO installation (name) VALUES
    ('Piscina Pequeña'),
    ('Piscina Grande'),
    ('Gimnasio'),
    ('Sala de Actividades 1'),
    ('Sala de Actividades 2'),
    ('Sala de Actividades 3'),
    ('Pista de Pádel 1'),
    ('Pista de Pádel 2'),
    ('Pista de Ténis 1'),
    ('Pista de Ténis 2');

CREATE TABLE IF NOT EXISTS category_installation (
    category TEXT NOT NULL
        CHECK (category IN (
            'Natación',
            'Pilates',
            'Acondicionamiento Físico',
            'Padel',
            'Tenis'
        )),
    installation_id INTEGER NOT NULL,
    PRIMARY KEY (category, installation_id),
    FOREIGN KEY (installation_id) REFERENCES installation (id)
);

INSERT OR IGNORE INTO category_installation (category, installation_id)
SELECT 'Natación', id FROM installation
WHERE name IN ('Piscina Pequeña', 'Piscina Grande');

INSERT OR IGNORE INTO category_installation (category, installation_id)
SELECT category, installation.id
FROM installation
CROSS JOIN (
    SELECT 'Pilates' AS category
    UNION ALL SELECT 'Acondicionamiento Físico'
)
WHERE installation.name IN (
    'Gimnasio',
    'Sala de Actividades 1',
    'Sala de Actividades 2',
    'Sala de Actividades 3'
);

INSERT OR IGNORE INTO category_installation (category, installation_id)
SELECT 'Padel', id FROM installation
WHERE name IN ('Pista de Pádel 1', 'Pista de Pádel 2');

INSERT OR IGNORE INTO category_installation (category, installation_id)
SELECT 'Tenis', id FROM installation
WHERE name IN ('Pista de Ténis 1', 'Pista de Ténis 2');

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL
        CHECK (category IN (
            'Natación',
            'Pilates',
            'Acondicionamiento Físico',
            'Padel',
            'Tenis'
        )),
    level TEXT NOT NULL
        CHECK (level IN ('Iniciación', 'Medio', 'Avanzado')),
    installation_id INTEGER,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    available_places INTEGER NOT NULL CHECK (available_places > 0),
    occupied_places INTEGER NOT NULL DEFAULT 0
        CHECK (occupied_places >= 0 AND occupied_places <= available_places),
    ini_socio TEXT,
    fin_socio TEXT,
    ini_no_socio TEXT,
    fin_no_socio TEXT,
    CHECK (end_time > start_time),
    FOREIGN KEY (category, installation_id)
        REFERENCES category_installation (category, installation_id)
);

CREATE TABLE IF NOT EXISTS activity_day (
    activity_id INTEGER NOT NULL,
    weekday TEXT NOT NULL
        CHECK (weekday IN (
            'Lunes',
            'Martes',
            'Miércoles',
            'Jueves',
            'Viernes',
            'Sábado',
            'Domingo'
        )),
    PRIMARY KEY (activity_id, weekday),
    FOREIGN KEY (activity_id) REFERENCES activity (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Socios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dni TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    numero_socio TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS Inscripciones (
    id_socio INTEGER NOT NULL,
    id_actividad INTEGER NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('confirmada', 'lista_espera')),
    fecha_solicitud DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_socio, id_actividad),
    FOREIGN KEY (id_socio) REFERENCES Socios (id),
    FOREIGN KEY (id_actividad) REFERENCES activity (id)
);
