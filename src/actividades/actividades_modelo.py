import sqlite3
from datetime import date
from pathlib import Path

from src.config import DATABASE


DB_PATH = DATABASE
DatabasePath = str | Path


def conectar(db_path: DatabasePath = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_actividades_disponibles(
    db_path: DatabasePath = DB_PATH,
) -> list[dict[str, object]]:
    conn = conectar(db_path)
    try:
        rows = conn.execute(
            """
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
            ORDER BY activity.id
            """
        ).fetchall()
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
            for activity in rows
        ]
    finally:
        conn.close()


def inscribir_socio(
    dni: str,
    id_actividad: int,
    db_path: DatabasePath = DB_PATH,
) -> dict[str, object]:
    conn = conectar(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        socio = conn.execute(
            "SELECT id, nombre, apellidos FROM socios WHERE dni = ?",
            (dni,),
        ).fetchone()
        if socio is None:
            raise ValueError("No se ha encontrado ningún socio con ese DNI.")

        actividad = conn.execute(
            """
            SELECT
                category, level, start_time, end_time,
                available_places, occupied_places,
                member_registration_start, member_registration_end
            FROM activity
            WHERE id = ?
            """,
            (id_actividad,),
        ).fetchone()
        if actividad is None:
            raise ValueError("La actividad seleccionada no existe.")

        duplicate = conn.execute(
            "SELECT 1 FROM inscripcion WHERE dni = ? AND activity_id = ?",
            (dni, id_actividad),
        ).fetchone()
        if duplicate:
            raise ValueError("El socio ya está inscrito en esta actividad.")

        _validate_member_registration_window(actividad)
        estado = "lista de espera"
        if actividad["occupied_places"] < actividad["available_places"]:
            estado = "confirmado"

        conn.execute(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado, es_socio
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                id_actividad,
                socio["nombre"],
                socio["apellidos"],
                dni,
                estado,
            ),
        )

        if estado == "confirmado":
            result = conn.execute(
                """
                UPDATE activity
                SET occupied_places = occupied_places + 1
                WHERE id = ? AND occupied_places < available_places
                """,
                (id_actividad,),
            )
            if result.rowcount != 1:
                raise sqlite3.DatabaseError(
                    "No se pudo actualizar la ocupación de la actividad."
                )

        weekdays = conn.execute(
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
        ).fetchall()
        conn.commit()
        return {
            "socio_id": socio["id"],
            "nombre": f"{socio['nombre']} {socio['apellidos']}",
            "actividad": actividad["category"],
            "nivel": actividad["level"],
            "periodicidad": (
                f"{', '.join(day['weekday'] for day in weekdays) or 'Días no definidos'}, "
                f"{actividad['start_time']}-{actividad['end_time']}"
            ),
            "estado": estado,
        }
       
    except sqlite3.IntegrityError:
        raise ValueError("El socio ya está inscrito en esta actividad.")


def get_inscripciones_cancelables(dni):
    conn = conectar()
    cursor = conn.cursor()
    
    # Obtiene solo las actividades a las que está inscrito y en plazo de cancelación
    query = """
        SELECT a.id, a.nombre, i.estado, a.fecha_limite_cancelacion
        FROM Actividades a
        JOIN Inscripciones i ON a.id = i.id_actividad
        JOIN Socios s ON i.id_socio = s.id
        WHERE s.dni = ? AND i.estado IN ('confirmada', 'lista_espera')
        AND a.fecha_limite_cancelacion >= CURRENT_DATE
    """
    cursor.execute(query, (dni,))
    actividades = cursor.fetchall()
    conn.close()
    return actividades

def cancelar_inscripcion(dni, id_actividad):
    conn = conectar()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM Socios WHERE dni = ?", (dni,))
        socio = cursor.fetchone()
        if not socio:
            raise ValueError("Socio no encontrado.")
            
        id_socio = socio['id']
        
        # Cancela la inscripción liberando la plaza y anula el pago asociado[cite: 24]
        cursor.execute("""
            UPDATE Inscripciones 
            SET estado = 'cancelada', estado_pago = 'anulado'
            WHERE id_socio = ? AND id_actividad = ? AND estado != 'cancelada'
        """, (id_socio, id_actividad))
        
        if cursor.rowcount == 0:
            raise ValueError("No se pudo cancelar. Verifica que estés inscrito y en plazo.")
            
        conn.commit()
        return True
    finally:
        conn.close()


def _validate_member_registration_window(activity: sqlite3.Row) -> None:
    period_start = activity["member_registration_start"]
    period_end = activity["member_registration_end"]
    if period_start is None and period_end is None:
        raise ValueError("No hay un plazo de inscripción para socios configurado.")
    if period_start is None or period_end is None:
        raise ValueError("El plazo de inscripción para socios está incompleto.")

    today = date.today().isoformat()
    if not period_start <= today <= period_end:
        raise ValueError(
            "La inscripción para socios no está abierta en la fecha actual."
        )
