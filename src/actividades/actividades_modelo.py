import sqlite3
from pathlib import Path

from src.config import DATABASE

DB_PATH = DATABASE


def conectar(db_path: str | Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_actividades_disponibles(db_path: str | Path = DB_PATH):
    conn = conectar(db_path)
    cursor = conn.cursor()

    query = """
        SELECT activity.id,
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
        ORDER BY activity.id
    """
    try:
        cursor.execute(query)
        actividades = []
        for activity in cursor.fetchall():
            weekdays = activity["weekdays"] or "Días no definidos"
            actividades.append({
                "id": activity["id"],
                "nombre": activity["category"],
                "modalidad": activity["installation"] or "Sin instalación",
                "nivel": activity["level"],
                "periodicidad": (
                    f"{weekdays}, {activity['start_time']}-{activity['end_time']}"
                ),
                "plazas_totales": activity["available_places"],
                "plazas_libres": max(
                    activity["available_places"] - activity["occupied_places"], 0
                ),
            })
        return actividades
    finally:
        conn.close()


def inscribir_socio(
    dni: str, id_actividad: int, db_path: str | Path = DB_PATH
) -> dict[str, str]:
    conn = conectar(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT id, nombre, apellidos, numero_socio FROM Socios WHERE dni = ?",
            (dni,),
        )
        socio = cursor.fetchone()
        if not socio:
            raise ValueError("No se ha encontrado ningún socio con ese DNI.")

        cursor.execute("""
            SELECT category, level, start_time, end_time, available_places,
                   occupied_places
            FROM activity
            WHERE id = ?
        """, (id_actividad,))
        actividad = cursor.fetchone()

        if not actividad:
            raise ValueError("La actividad seleccionada no existe.")

        cursor.execute(
            """
            SELECT 1 FROM Inscripciones
            WHERE id_socio = ? AND id_actividad = ?
            """,
            (socio["id"], id_actividad),
        )
        if cursor.fetchone():
            raise ValueError("El socio ya está inscrito en esta actividad.")

        estado_inscripcion = "lista_espera"
        if actividad["occupied_places"] < actividad["available_places"]:
            estado_inscripcion = "confirmada"

        cursor.execute("""
            INSERT INTO Inscripciones (id_socio, id_actividad, estado)
            VALUES (?, ?, ?)
        """, (socio["id"], id_actividad, estado_inscripcion))

        if estado_inscripcion == "confirmada":
            cursor.execute(
                """
                UPDATE activity
                SET occupied_places = occupied_places + 1
                WHERE id = ? AND occupied_places < available_places
                """,
                (id_actividad,),
            )
            if cursor.rowcount != 1:
                raise sqlite3.DatabaseError(
                    "No se pudo actualizar la ocupación de la actividad."
                )

        weekdays = ", ".join(
            activity["weekday"]
            for activity in conn.execute(
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
                (id_actividad,),
            )
        )
        conn.commit()
        return {
            "nombre": f"{socio['nombre']} {socio['apellidos']}",
            "numero_socio": socio["numero_socio"],
            "actividad": actividad["category"],
            "nivel": actividad["level"],
            "periodicidad": (
                f"{weekdays or 'Días no definidos'}, "
                f"{actividad['start_time']}-{actividad['end_time']}"
            ),
            "estado": estado_inscripcion
        }
    except (ValueError, sqlite3.Error):
        conn.rollback()
        raise
    finally:
        conn.close()