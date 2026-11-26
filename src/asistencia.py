from datetime import date, timedelta

from src.activities import list_activities
from src.util.database import DataBase
from src.util.pretty_tables import print_table


_WEEKDAYS = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


def iniciar_registro_asistencia(database: DataBase) -> None:
    activities = list_activities(database)
    if not activities:
        print("Todavía no hay actividades disponibles.")
        return

    print_table(
        "ACTIVIDADES DISPONIBLES",
        ["ID", "Categoría", "Nivel", "Instalación"],
        [
            [
                activity["id"],
                activity["category"],
                activity["level"],
                activity["installation"] or "Sin instalación",
            ]
            for activity in activities
        ],
    )

    try:
        activity_id = int(input("\nIntroduce el ID de la actividad: ").strip())
    except ValueError:
        print("El identificador de actividad debe ser numérico.")
        return

    activity = next(
        (item for item in activities if item["id"] == activity_id),
        None,
    )
    if activity is None:
        print("No existe una actividad con ese ID.")
        return

    weekdays = activity["weekdays"]
    if not weekdays:
        print("La actividad no tiene días de sesión configurados.")
        return

    sessions = _get_recordable_sessions(activity, date.today())
    if not sessions:
        print("No hay sesiones pasadas o de hoy disponibles para registrar.")
        return
    print_table(
        "SESIONES RECIENTES",
        ["Opción", "Día", "Fecha", "Horario"],
        [
            [
                index,
                _WEEKDAYS[session_date.weekday()],
                session_date.strftime("%d/%m/%Y"),
                f"{activity['start_time']}-{activity['end_time']}",
            ]
            for index, session_date in enumerate(sessions, start=1)
        ],
    )

    try:
        session_index = int(input("Selecciona una sesión: ").strip()) - 1
    except ValueError:
        print("La sesión debe seleccionarse mediante su número.")
        return
    if not 0 <= session_index < len(sessions):
        print("La sesión seleccionada no es válida.")
        return

    session_date = sessions[session_index]
    weekday = _WEEKDAYS[session_date.weekday()]

    saved_session = database.executeQuery(
        """
        SELECT planned_count
        FROM attendance_session
        WHERE activity_id = ? AND session_date = ?
        """,
        activity_id,
        session_date.isoformat(),
    )
    if saved_session:
        registrations = database.executeQuery(
            """
            SELECT
                inscripcion.id,
                inscripcion.nombre,
                inscripcion.apellidos,
                inscripcion.es_socio
            FROM attendance_record
            JOIN inscripcion ON inscripcion.id = attendance_record.registration_id
            WHERE attendance_record.activity_id = ?
              AND attendance_record.session_date = ?
            ORDER BY inscripcion.apellidos, inscripcion.nombre, inscripcion.id
            """,
            activity_id,
            session_date.isoformat(),
        )
        print("Ya existe un registro; puedes corregirlo para esta sesión.")
    else:
        registrations = database.executeQuery(
            """
            SELECT
                inscripcion.id,
                inscripcion.nombre,
                inscripcion.apellidos,
                inscripcion.es_socio
            FROM inscripcion
            WHERE inscripcion.activity_id = ?
              AND inscripcion.estado = 'confirmado'
            ORDER BY inscripcion.apellidos, inscripcion.nombre, inscripcion.id
            """,
            activity_id,
        )

    print_table(
        "REGISTRO DE ASISTENCIA",
        ["Actividad", "Día", "Fecha", "Horario"],
        [[
            f"{activity['category']} - {activity['level']}",
            weekday,
            session_date.isoformat(),
            f"{activity['start_time']}-{activity['end_time']}",
        ]],
    )

    entries = []
    for registration in registrations:
        member = "Sí" if registration["es_socio"] else "No"
        while True:
            selection = input(
                f"{registration['nombre']} {registration['apellidos']} | "
                f"Socio: {member} | Presente/Ausente (P/A)"
                ": "
            ).strip().lower()
            if selection in {"p", "presente"}:
                entries.append((registration["id"], True))
                break
            if selection in {"a", "ausente"}:
                entries.append((registration["id"], False))
                break
            print("Indica P para presente o A para ausente.")

    present_count = sum(1 for _, present in entries if present)
    enrolled_count = len(entries)
    absent_count = enrolled_count - present_count
    attendance_percentage = (
        round(present_count / enrolled_count * 100, 1) if enrolled_count else 0.0
    )
    capacity = activity["available_places"]
    occupancy_percentage = (
        round(present_count / capacity * 100, 1) if capacity else 0.0
    )

    print_table(
        "RESUMEN DE ASISTENCIA",
        ["Inscritos", "Presentes", "Ausentes", "Asistencia", "Ocupación"],
        [[
            enrolled_count,
            present_count,
            absent_count,
            f"{attendance_percentage}%",
            f"{occupancy_percentage}% ({present_count}/{capacity} plazas)",
        ]],
    )
    save_attendance_session(
        database,
        activity_id,
        session_date,
        dict(entries),
        today=date.today(),
    )
    print("El registro de asistencia se ha guardado o actualizado.")


def save_attendance_session(
    database: DataBase,
    activity_id: int,
    session_date: date,
    attendance: dict[int, bool],
    today: date | None = None,
) -> None:
    current_date = today or date.today()
    if session_date > current_date:
        raise ValueError("No se puede registrar asistencia para una fecha futura.")

    activity = database.executeQuery(
        "SELECT start_date FROM activity WHERE id = ?",
        activity_id,
    )
    if not activity:
        raise ValueError("No existe la actividad seleccionada.")
    if (
        activity[0]["start_date"] is not None
        and session_date < date.fromisoformat(str(activity[0]["start_date"]))
    ):
        raise ValueError("La fecha es anterior al inicio de la actividad.")

    weekday = _WEEKDAYS[session_date.weekday()]
    scheduled_day = database.executeQuery(
        "SELECT 1 FROM activity_day WHERE activity_id = ? AND weekday = ?",
        activity_id,
        weekday,
    )
    if not scheduled_day:
        raise ValueError("La actividad no está programada para esa fecha.")

    session_date_text = session_date.isoformat()
    existing_session = database.executeQuery(
        """
        SELECT planned_count
        FROM attendance_session
        WHERE activity_id = ? AND session_date = ?
        """,
        activity_id,
        session_date_text,
    )
    if existing_session:
        registrations = database.executeQuery(
            """
            SELECT registration_id
            FROM attendance_record
            WHERE activity_id = ? AND session_date = ?
            """,
            activity_id,
            session_date_text,
        )
        registration_ids = {
            int(registration["registration_id"]) for registration in registrations
        }
        planned_count = int(existing_session[0]["planned_count"])
        if len(registration_ids) != planned_count:
            raise ValueError(
                "No se puede corregir la sesión porque faltan inscripciones "
                "del registro original."
            )
    else:
        registrations = database.executeQuery(
            """
            SELECT id
            FROM inscripcion
            WHERE activity_id = ? AND estado = 'confirmado'
            """,
            activity_id,
        )
        registration_ids = {
            int(registration["id"]) for registration in registrations
        }
        planned_count = len(registration_ids)
    if any(type(registration_id) is not int for registration_id in attendance):
        raise ValueError("Los identificadores de inscripción deben ser enteros.")
    if any(type(present) is not bool for present in attendance.values()):
        raise ValueError("La asistencia debe indicarse como presente o ausente.")
    if set(attendance) != registration_ids:
        raise ValueError(
            "Debe indicar presente o ausente para todas las inscripciones confirmadas."
        )

    queries = [
        (
            """
            INSERT INTO attendance_session (activity_id, session_date, planned_count)
            VALUES (?, ?, ?)
            ON CONFLICT (activity_id, session_date)
            DO UPDATE SET planned_count = excluded.planned_count
            """,
            (activity_id, session_date_text, planned_count),
        ),
        (
            """
            DELETE FROM attendance_record
            WHERE activity_id = ? AND session_date = ?
            """,
            (activity_id, session_date_text),
        ),
    ]
    queries.extend(
        (
            """
            INSERT INTO attendance_record (
                activity_id, session_date, registration_id, attended
            ) VALUES (?, ?, ?, ?)
            """,
            (activity_id, session_date_text, registration_id, int(present)),
        )
        for registration_id, present in sorted(attendance.items())
    )
    database.executeTransactionQueries(queries)


def _get_recordable_sessions(
    activity: dict[str, object], today: date, count: int = 4
) -> list[date]:
    weekdays = activity["weekdays"]
    scheduled_weekdays = {
        index for index, weekday in enumerate(_WEEKDAYS) if weekday in weekdays
    }
    start_date = (
        date.fromisoformat(str(activity["start_date"]))
        if activity["start_date"] is not None
        else date.min
    )

    sessions = []
    current_date = today
    while len(sessions) < count and current_date >= start_date:
        if current_date.weekday() in scheduled_weekdays:
            sessions.append(current_date)
        current_date -= timedelta(days=1)
    return list(reversed(sessions))
