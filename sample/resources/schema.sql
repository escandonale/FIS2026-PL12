--Primero se deben borrar todas las tablas (de detalle a maestro) y lugo anyadirlas (de maestro a detalle)

drop table if exists Employee;
drop table if exists Company;

create table Company (id int not null primary key, id2 int, name varchar(32), startDate varchar(10));
create table Employee (id int not null primary key, name varchar(32), 
                       salary int, birthDate varchar(10), idCompany int not null,
                       foreign key (idCompany) references Company (id), check (birthDate<"2010-01-01")
                      );

DROP TABLE IF EXISTS Inscripciones;
DROP TABLE IF EXISTS Actividades;
DROP TABLE IF EXISTS Socios;

CREATE TABLE Socios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dni TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    numero_socio TEXT UNIQUE NOT NULL
);

CREATE TABLE Actividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    modalidad TEXT NOT NULL,
    nivel TEXT NOT NULL,
    periodicidad TEXT NOT NULL,
    plazas_totales INTEGER NOT NULL
);

CREATE TABLE Inscripciones (
    id_socio INTEGER,
    id_actividad INTEGER,
    estado TEXT NOT NULL, -- 'confirmada' o 'lista_espera'
    fecha_solicitud DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_socio, id_actividad),
    FOREIGN KEY (id_socio) REFERENCES Socios(id),
    FOREIGN KEY (id_actividad) REFERENCES Actividades(id)
);