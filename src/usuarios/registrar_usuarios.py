import sqlite3
from datetime import date
from pathlib import Path

from src.config import DATABASE
from src.util.database import DataBase


def conectar(db_path: str | Path = DATABASE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrar_genero(database: DataBase) -> None:
    socios_columns = {
        column["name"] for column in database.executeQuery("PRAGMA table_info(Socios)")
    }
    if "genero" not in socios_columns:
        database.executeUpdateQuery("ALTER TABLE Socios ADD COLUMN genero TEXT")

    database.executeScriptFromString(
        """
        CREATE TRIGGER IF NOT EXISTS validate_member_gender_insert
        BEFORE INSERT ON Socios
        WHEN NEW.genero NOT IN ('m', 'f', 'n') OR NEW.genero IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'El género debe ser m, f o n.');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_member_gender_update
        BEFORE UPDATE OF genero ON Socios
        WHEN NEW.genero NOT IN ('m', 'f', 'n') OR NEW.genero IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'El género debe ser m, f o n.');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_non_member_gender_insert
        BEFORE INSERT ON no_socio
        WHEN NEW.genero NOT IN ('m', 'f', 'n') OR NEW.genero IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'El género debe ser m, f o n.');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_non_member_gender_update
        BEFORE UPDATE OF genero ON no_socio
        WHEN NEW.genero NOT IN ('m', 'f', 'n') OR NEW.genero IS NULL
        BEGIN
            SELECT RAISE(ABORT, 'El género debe ser m, f o n.');
        END;
        """
    )


def _validar_genero(genero: str) -> str:
    normalized_gender = genero.strip().lower()
    if normalized_gender not in {"m", "f", "n"}:
        raise ValueError("El género debe ser m, f o n.")
    return normalized_gender


def _validar_fecha_nacimiento(fecha_nacimiento: str) -> date:
    if not fecha_nacimiento or not fecha_nacimiento.strip():
        raise ValueError("La fecha de nacimiento es obligatoria.")

    try:
        parsed = date.fromisoformat(fecha_nacimiento.strip())
    except ValueError as error:
        raise ValueError("La fecha de nacimiento debe tener el formato AAAA-MM-DD.") from error

    if parsed.isoformat() != fecha_nacimiento.strip():
        raise ValueError("La fecha de nacimiento debe tener el formato AAAA-MM-DD.")
    if parsed > date.today():
        raise ValueError("La fecha de nacimiento no puede ser futura.")

    return parsed


def registrar_socio(
    nombre: str,
    apellidos: str,
    genero: str,
    dni: str,
    numero_socio: str,
    direccion: str,
    db_path: str | Path = DATABASE,
) -> str:
    nombre = nombre.strip()
    apellidos = apellidos.strip()
    genero = _validar_genero(genero)
    dni = dni.strip()
    numero_socio = numero_socio.strip()
    direccion = direccion.strip()

    if not all([nombre, apellidos, dni, numero_socio, direccion]):
        raise ValueError("Todos los campos del socio son obligatorios.")

    conn = conectar(db_path)
    try:
        if conn.execute(
            "SELECT 1 FROM Socios WHERE dni = ?",
            (dni,),
        ).fetchone():
            raise ValueError("Ya existe un socio registrado con este DNI.")
        if conn.execute(
            "SELECT 1 FROM no_socio WHERE dni = ?",
            (dni,),
        ).fetchone():
            raise ValueError(
                "El DNI ya está registrado como no socio; no se puede crear "
                "un segundo perfil."
            )
        if conn.execute(
            "SELECT 1 FROM Socios WHERE numero_socio = ?",
            (numero_socio,),
        ).fetchone():
            raise ValueError("Ya existe un socio registrado con ese número de socio.")

        conn.execute(
            """
            INSERT INTO Socios (
                nombre, apellidos, dni, numero_socio, direccion, genero
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nombre, apellidos, dni, numero_socio, direccion, genero),
        )
        conn.commit()
        socio = conn.execute(
            "SELECT dni FROM Socios WHERE dni = ?",
            (dni,),
        ).fetchone()
        if socio is None:
            raise ValueError("No se pudo confirmar el alta del socio.")
        return dni
    except sqlite3.Error as error:
        conn.rollback()
        raise ValueError(f"No se pudo registrar el socio: {error}") from error
    finally:
        conn.close()


def registrar_no_socio(
    nombre: str,
    apellidos: str,
    fecha_nacimiento: str,
    genero: str,
    direccion: str,
    dni: str,
    correo: str,
    db_path: str | Path = DATABASE,
) -> str:
    nombre = nombre.strip()
    apellidos = apellidos.strip()
    genero = genero.strip()
    direccion = direccion.strip()
    dni = dni.strip()
    correo = correo.strip()

    if not all([nombre, apellidos, genero, direccion, dni, correo]):
        raise ValueError("Todos los campos del usuario son obligatorios.")

    genero = _validar_genero(genero)
    _validar_fecha_nacimiento(fecha_nacimiento)

    if "@" not in correo or "." not in correo:
        raise ValueError("El correo electrónico no tiene un formato válido.")

    conn = conectar(db_path)
    try:
        existente = conn.execute(
            "SELECT 1 FROM no_socio WHERE dni = ?",
            (dni,),
        ).fetchone()

        if existente:
            raise ValueError("Ya existe un usuario registrado con este DNI.")
        socio = conn.execute(
            "SELECT 1 FROM Socios WHERE dni = ?",
            (dni,),
        ).fetchone()
        if socio:
            raise ValueError(
                "El DNI ya está registrado como socio; utiliza ese perfil."
            )

        conn.execute(
            """
            INSERT INTO no_socio (
                nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nombre, apellidos, fecha_nacimiento.strip(), genero, direccion, dni, correo),
        )
        conn.commit()

        usuario = conn.execute(
            "SELECT fecha_registro FROM no_socio WHERE dni = ?",
            (dni,),
        ).fetchone()

        if usuario is None:
            raise ValueError("No se pudo recuperar el registro del usuario.")

        return usuario["fecha_registro"]
    except sqlite3.Error as error:
        conn.rollback()
        raise ValueError(f"No se pudo registrar el usuario: {error}") from error
    finally:
        conn.close()