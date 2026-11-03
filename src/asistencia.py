from datetime import date, timedelta

from src.activities import list_activities
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


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

    print("\nACTIVIDADES DISPONIBLES")
    for activity in activities:
        print(
            f"[{activity['id']}] {activity['category']} - {activity['level']} | "
            f"{activity['installation'] or 'Sin instalación'}"
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

    sessions = _get_upcoming_sessions(activity, date.today())
    print("\nPRÓXIMAS SESIONES")
    for index, session_date in enumerate(sessions, start=1):
        weekday = _WEEKDAYS[session_date.weekday()]
        print(
            f"{index}. {weekday} {session_date.strftime('%d/%m/%Y')} | "
            f"{activity['start_time']}-{activity['end_time']}"
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

    print(
        f"\nREGISTRO DE ASISTENCIA: {activity['category']} | "
        f"{weekday} {session_date.isoformat()} | "
        f"{activity['start_time']}-{activity['end_time']}"
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

    print("\nRESUMEN DE ASISTENCIA")
    print(f"Inscritos: {enrolled_count}")
    print(f"Presentes: {present_count}")
    print(f"Ausentes: {absent_count}")
    print(f"Porcentaje de asistencia: {attendance_percentage}%")
    print(
        f"Porcentaje de ocupación: {occupancy_percentage}% "
        f"({present_count}/{capacity} plazas de la actividad)"
    )
    print("Resumen generado. No se ha guardado el registro de asistencia.")


def _get_upcoming_sessions(
    activity: dict[str, object], today: date, count: int = 4
) -> list[date]:
    weekdays = activity["weekdays"]
    scheduled_weekdays = {
        index for index, weekday in enumerate(_WEEKDAYS) if weekday in weekdays
    }
    start_date = activity["start_date"]
    first_date = today
    if start_date is not None:
        first_date = max(today, date.fromisoformat(str(start_date)))

    sessions = []
    current_date = first_date
    while len(sessions) < count:
        if current_date.weekday() in scheduled_weekdays:
            sessions.append(current_date)
        current_date += timedelta(days=1)
    return sessions
