import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict

from src.config import DATABASE
from src.util.database import DataBase


DatabasePath = str | Path
DB_PATH = DATABASE


class ActivityForRegistration(TypedDict):
    id: int
    nombre: str
    modalidad: str
    nivel: str
    periodicidad: str
    plazas_totales: int
    plazas_libres: int


def conectar(db_path: DatabasePath = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate_cancellation_status(database: DataBase) -> None:
    tables = database.executeQuery(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'inscripcion'"
    )
    if not tables or "'cancelada'" in (tables[0]["sql"] or ""):
        return

    column_names = {
        column["name"]
        for column in database.executeQuery("PRAGMA table_info(inscripcion)")
    }
    expressions = {
        "id": "id" if "id" in column_names else "NULL",
        "activity_id": "activity_id",
        "nombre": "nombre",
        "apellidos": "apellidos",
        "dni": "dni",
        "estado": "estado",
        "fecha_inscripcion": (
            "fecha_inscripcion"
            if "fecha_inscripcion" in column_names
            else "CURRENT_TIMESTAMP"
        ),
        "es_socio": "es_socio" if "es_socio" in column_names else "0",
    }
    database.executeScriptFromString(
        f"""
        PRAGMA foreign_keys = OFF;
        BEGIN;
        CREATE TABLE inscripcion_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            apellidos TEXT NOT NULL,
            dni TEXT NOT NULL,
            estado TEXT NOT NULL
                CHECK (estado IN ('confirmado', 'lista de espera', 'cancelada')),
            fecha_inscripcion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            es_socio INTEGER NOT NULL DEFAULT 0 CHECK (es_socio IN (0, 1)),
            FOREIGN KEY (activity_id) REFERENCES activity (id)
        );
        INSERT INTO inscripcion_new (
            id, activity_id, nombre, apellidos, dni, estado,
            fecha_inscripcion, es_socio
        )
        SELECT
            {expressions["id"]}, {expressions["activity_id"]},
            {expressions["nombre"]}, {expressions["apellidos"]},
            {expressions["dni"]}, {expressions["estado"]},
            {expressions["fecha_inscripcion"]}, {expressions["es_socio"]}
        FROM inscripcion;
        DROP TABLE inscripcion;
        ALTER TABLE inscripcion_new RENAME TO inscripcion;
        COMMIT;
        PRAGMA foreign_keys = ON;
        """
    )


def get_actividades_disponibles(
    db_path: DatabasePath = DB_PATH,
    es_socio: bool | None = None,
) -> list[ActivityForRegistration]:
    connection = conectar(db_path)
    try:
        query = """
            SELECT
                activity.id,
                activity.category,
                activity.level,
                installation.name AS installation,
                activity.start_time,
                activity.end_time,
                activity.available_places,
                activity.occupied_places,
                (
                    SELECT group_concat(weekday, ', ')
                    FROM (
                        SELECT weekday
                        FROM activity_day
                        WHERE activity_id = activity.id
                        ORDER BY CASE weekday
                            WHEN 'Lunes' THEN 1
                            WHEN 'Martes' THEN 2
                            WHEN 'Miércoles' THEN 3
                            WHEN 'Jueves' THEN 4
                            WHEN 'Viernes' THEN 5
                            WHEN 'Sábado' THEN 6
                            WHEN 'Domingo' THEN 7
                        END
                    )
                ) AS weekdays
            FROM activity
            LEFT JOIN installation
                ON installation.id = activity.installation_id
        """
        parameters: tuple[str, ...] = ()
        if es_socio is not None:
            start_column = (
                "member_registration_start"
                if es_socio
                else "non_member_registration_start"
            )
            end_column = (
                "member_registration_end"
                if es_socio
                else "non_member_registration_end"
            )
            today = date.today().isoformat()
            query += (
                f"WHERE activity.{start_column} <= ? "
                f"AND activity.{end_column} >= ? "
            )
            parameters = (today, today)
        query += "ORDER BY activity.id"
        activities = connection.execute(query, parameters).fetchall()
        return [
            {
                "id": activity["id"],
                "nombre": activity["category"],
                "modalidad": activity["installation"] or "Sin instalación",
                "nivel": activity["level"],
                "periodicidad": (
                    f"{activity['weekdays'] or 'Días no definidos'}, "
                    f"{activity['start_time']}-{activity['end_time']}"
                ),
                "plazas_totales": activity["available_places"],
                "plazas_libres": max(
                    activity["available_places"] - activity["occupied_places"], 0
                ),
            }
            for activity in activities
        ]
    finally:
        connection.close()


def inscribir_socio(
    dni: str,
    id_actividad: int,
    db_path: DatabasePath = DB_PATH,
    today: date | None = None,
) -> dict[str, object]:
    connection = conectar(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        socio = connection.execute(
            "SELECT id, nombre, apellidos FROM Socios WHERE dni = ?",
            (dni.strip(),),
        ).fetchone()
        if socio is None:
            raise ValueError("No se ha encontrado ningún socio con ese DNI.")
        return _crear_inscripcion(
            connection,
            dni.strip(),
            id_actividad,
            socio["nombre"],
            socio["apellidos"],
            True,
            today or date.today(),
        )
    except (ValueError, sqlite3.Error):
        connection.rollback()
        raise
    finally:
        connection.close()


def inscribir_no_socio(
    dni: str,
    nombre: str,
    apellidos: str,
    id_actividad: int,
    db_path: DatabasePath = DB_PATH,
    today: date | None = None,
) -> dict[str, object]:
    normalized_dni = dni.strip()
    normalized_name = nombre.strip()
    normalized_surname = apellidos.strip()
    if not normalized_dni or not normalized_name or not normalized_surname:
        raise ValueError("DNI, nombre y apellidos son obligatorios.")

    connection = conectar(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        socio = connection.execute(
            "SELECT 1 FROM Socios WHERE dni = ?",
            (normalized_dni,),
        ).fetchone()
        if socio is not None:
            raise ValueError(
                "El DNI pertenece a un socio; utiliza la inscripción de socio."
            )
        return _crear_inscripcion(
            connection,
            normalized_dni,
            id_actividad,
            normalized_name,
            normalized_surname,
            False,
            today or date.today(),
        )
    except (ValueError, sqlite3.Error):
        connection.rollback()
        raise
    finally:
        connection.close()


def _crear_inscripcion(
    connection: sqlite3.Connection,
    dni: str,
    activity_id: int,
    nombre: str,
    apellidos: str,
    es_socio: bool,
    today: date,
) -> dict[str, object]:
    activity = connection.execute(
        """
        SELECT
            category, level, start_time, end_time,
            available_places, occupied_places,
            member_registration_start, member_registration_end,
            non_member_registration_start, non_member_registration_end
        FROM activity
        WHERE id = ?
        """,
        (activity_id,),
    ).fetchone()
    if activity is None:
        raise ValueError("La actividad seleccionada no existe.")

    duplicate = connection.execute(
        """
        SELECT 1
        FROM inscripcion
        WHERE dni = ? AND activity_id = ?
          AND estado IN ('confirmado', 'lista de espera')
        """,
        (dni, activity_id),
    ).fetchone()
    if duplicate:
        raise ValueError("El DNI ya está inscrito en esta actividad.")

    _validate_registration_window(activity, es_socio, today)
    state = "lista de espera"
    if activity["occupied_places"] < activity["available_places"]:
        state = "confirmado"

    connection.execute(
        """
        INSERT INTO inscripcion (
            activity_id, nombre, apellidos, dni, estado, es_socio
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (activity_id, nombre, apellidos, dni, state, int(es_socio)),
    )
    if state == "confirmado":
        result = connection.execute(
            """
            UPDATE activity
            SET occupied_places = occupied_places + 1
            WHERE id = ? AND occupied_places < available_places
            """,
            (activity_id,),
        )
        if result.rowcount != 1:
            raise sqlite3.DatabaseError(
                "No se pudo actualizar la ocupación de la actividad."
            )

    weekdays = connection.execute(
        """
        SELECT weekday
        FROM activity_day
        WHERE activity_id = ?
        ORDER BY CASE weekday
            WHEN 'Lunes' THEN 1
            WHEN 'Martes' THEN 2
            WHEN 'Miércoles' THEN 3
            WHEN 'Jueves' THEN 4
            WHEN 'Viernes' THEN 5
            WHEN 'Sábado' THEN 6
            WHEN 'Domingo' THEN 7
        END
        """,
        (activity_id,),
    ).fetchall()
    connection.commit()
    return {
        "nombre": f"{nombre} {apellidos}",
        "actividad": activity["category"],
        "nivel": activity["level"],
        "periodicidad": (
            f"{', '.join(day['weekday'] for day in weekdays) or 'Días no definidos'}, "
            f"{activity['start_time']}-{activity['end_time']}"
        ),
        "estado": state,
    }


def _validate_registration_window(
    activity: sqlite3.Row, es_socio: bool, today: date
) -> None:
    if es_socio:
        start_column = "member_registration_start"
        end_column = "member_registration_end"
        group_name = "socios"
    else:
        start_column = "non_member_registration_start"
        end_column = "non_member_registration_end"
        group_name = "no socios"

    period_start = activity[start_column]
    period_end = activity[end_column]
    if period_start is None and period_end is None:
        raise ValueError(
            f"No hay un plazo de inscripción para {group_name} configurado."
        )
    if period_start is None or period_end is None:
        raise ValueError(f"El plazo de inscripción para {group_name} está incompleto.")

    current_date = today.isoformat()
    if not period_start <= current_date <= period_end:
        raise ValueError(
            f"La inscripción para {group_name} no está abierta en la fecha actual."
        )


def _fecha_limite_cancelacion(start_date: str) -> date:
    activity_date = date.fromisoformat(start_date)
    first_day_of_month = activity_date.replace(day=1)
    return first_day_of_month - timedelta(days=15)


def get_inscripciones_cancelables(
    dni: str,
    db_path: DatabasePath = DB_PATH,
    today: date | None = None,
) -> list[dict[str, object]]:
    current_date = today or date.today()
    connection = conectar(db_path)
    try:
        registrations = connection.execute(
            """
            SELECT
                activity.id,
                activity.category AS nombre,
                activity.start_date,
                inscripcion.estado
            FROM inscripcion
            JOIN activity ON activity.id = inscripcion.activity_id
            WHERE inscripcion.dni = ?
              AND inscripcion.estado IN ('confirmado', 'lista de espera')
              AND activity.start_date IS NOT NULL
            ORDER BY activity.start_date, activity.id
            """,
            (dni.strip(),),
        ).fetchall()
        cancellable = []
        for registration in registrations:
            deadline = _fecha_limite_cancelacion(registration["start_date"])
            if deadline >= current_date:
                cancellable.append(
                    {
                        "id": registration["id"],
                        "nombre": registration["nombre"],
                        "estado": registration["estado"],
                        "fecha_limite_cancelacion": deadline.isoformat(),
                    }
                )
        return cancellable
    finally:
        connection.close()


def cancelar_inscripcion(
    dni: str,
    id_actividad: int,
    db_path: DatabasePath = DB_PATH,
    today: date | None = None,
) -> bool:
    current_date = today or date.today()
    connection = conectar(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        registration = connection.execute(
            """
            SELECT
                inscripcion.id,
                inscripcion.estado,
                activity.start_date
            FROM inscripcion
            JOIN activity ON activity.id = inscripcion.activity_id
            WHERE inscripcion.dni = ?
              AND activity.id = ?
              AND inscripcion.estado IN ('confirmado', 'lista de espera')
            """,
            (dni.strip(), id_actividad),
        ).fetchone()
        if registration is None:
            raise ValueError("No existe una inscripción activa para esa actividad.")
        if registration["start_date"] is None:
            raise ValueError("La actividad no tiene fecha de inicio configurada.")
        deadline = _fecha_limite_cancelacion(registration["start_date"])
        if current_date > deadline:
            raise ValueError(
                f"El plazo de cancelación terminó el {deadline.isoformat()}."
            )

        connection.execute(
            "UPDATE inscripcion SET estado = 'cancelada' WHERE id = ?",
            (registration["id"],),
        )
        if registration["estado"] == "confirmado":
            waiting = connection.execute(
                """
                SELECT id
                FROM inscripcion
                WHERE activity_id = ? AND estado = 'lista de espera'
                ORDER BY fecha_inscripcion, id
                LIMIT 1
                """,
                (id_actividad,),
            ).fetchone()
            if waiting is not None:
                connection.execute(
                    "UPDATE inscripcion SET estado = 'confirmado' WHERE id = ?",
                    (waiting["id"],),
                )
            else:
                result = connection.execute(
                    """
                    UPDATE activity
                    SET occupied_places = occupied_places - 1
                    WHERE id = ? AND occupied_places > 0
                    """,
                    (id_actividad,),
                )
                if result.rowcount != 1:
                    raise sqlite3.DatabaseError(
                        "La ocupación no coincide con las inscripciones confirmadas."
                    )
        connection.commit()
        return True
    except (ValueError, sqlite3.Error):
        connection.rollback()
        raise
    finally:
        connection.close()
