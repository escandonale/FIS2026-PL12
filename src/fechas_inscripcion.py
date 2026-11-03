import datetime as dt
import sqlite3
from datetime import date

DB_PATH = "centro_deportivo.db"


def conectar(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _parse_dt(value):
    if value is None:
        raise ValueError("La fecha no puede ser nula.")
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(text, fmt)
            except ValueError:
                continue
    raise ValueError(f"Formato de fecha no válido: {value!r}")


def validar_fecha(start_date, ini_s, fin_s, ini_nos, fin_nos):
    hoy = dt.datetime.now()
    start_dt = _parse_dt(start_date)
    ini_s_dt = _parse_dt(ini_s)
    fin_s_dt = _parse_dt(fin_s)
    ini_nos_dt = _parse_dt(ini_nos)
    fin_nos_dt = _parse_dt(fin_nos)

    if ini_s_dt < hoy or ini_nos_dt < hoy:
        raise ValueError("La fecha de apertura no puede ser anterior a la fecha actual.")

    if fin_s_dt <= ini_s_dt:
        raise ValueError("La fecha de cierre de socios debe ser posterior a su apertura.")

    if fin_nos_dt <= ini_nos_dt:
        raise ValueError("La fecha de cierre de no socios debe ser posterior a su apertura.")

    if ini_s_dt >= ini_nos_dt:
        raise ValueError("El periodo de socios debe comenzar antes que el de no socios.")

    if ini_nos_dt < fin_s_dt:
        raise ValueError("Los periodos no pueden solaparse; el de no socios debe empezar tras finalizar el de socios.")

    if fin_s_dt > start_dt or fin_nos_dt > start_dt:
        raise ValueError("Los plazos de inscripción deben finalizar antes de que comience la actividad.")

    return True


def plazo_inscripcion(db_path: str = DB_PATH):
    conn = conectar(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, category, level, start_time
            FROM activity
            WHERE start_time IS NOT NULL
            ORDER BY id
            """
        )
        actividades = cursor.fetchall()

        if not actividades:
            print("No hay actividades disponibles.")
            return

        for act in actividades:
            start_value = act["start_time"]
            if start_value and len(start_value) >= 10 and "-" in start_value:
                inicio = start_value
            else:
                inicio = "sin fecha definida"
            print(
                f"ID: {act['id']} | Categoría: {act['category']} | Nivel: {act['level']} | "
                f"Inicio: {inicio}"
            )

        id_elegido = int(input("Introduce el ID de la actividad que deseas configurar: ").strip())
        actividad_seleccionada = next((a for a in actividades if a["id"] == id_elegido), None)
        if not actividad_seleccionada:
            raise ValueError("El ID introducido no es válido.")

        start_value = actividad_seleccionada["start_time"]
        if start_value and "-" in start_value:
            start_date_dt = dt.datetime.strptime(start_value, "%Y-%m-%d %H:%M")
        elif start_value and ":" in start_value:
            today = date.today()
            start_date_dt = dt.datetime.combine(today, dt.time.fromisoformat(start_value))
        else:
            start_date_dt = dt.datetime.now()

        apertura_socios = _parse_dt(input("Inicio plazo socios: ").strip())
        cierre_socios = _parse_dt(input("Cierre plazo socios: ").strip())
        apertura_no_socios = _parse_dt(input("Inicio plazo no socios: ").strip())
        cierre_no_socios = _parse_dt(input("Cierre plazo no socios: ").strip())

        validar_fecha(start_date_dt, apertura_socios, cierre_socios, apertura_no_socios, cierre_no_socios)

        cursor.execute(
            """
            UPDATE activity
            SET ini_socio = ?,
                fin_socio = ?,
                ini_no_socio = ?,
                fin_no_socio = ?
            WHERE id = ?
            """,
            (
                apertura_socios.strftime("%Y-%m-%d %H:%M"),
                cierre_socios.strftime("%Y-%m-%d %H:%M"),
                apertura_no_socios.strftime("%Y-%m-%d %H:%M"),
                cierre_no_socios.strftime("%Y-%m-%d %H:%M"),
                id_elegido,
            ),
        )
        conn.commit()
        print("Fechas de inscripción configuradas correctamente.")
    except ValueError as error:
        print(f"Error al configurar los plazos de inscripción: {error}")
    finally:
        conn.close()
