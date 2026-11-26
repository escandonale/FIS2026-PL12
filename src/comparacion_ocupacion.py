from datetime import date, timedelta
from typing import TypedDict

from src.util.database import DataBase
from src.util.pretty_tables import print_table


WEEKDAYS = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)


class SessionComparison(TypedDict):
    activity_id: int
    activity: str
    session_date: str
    weekday: str
    schedule: str
    planned_count: int
    capacity: int
    planned_capacity_percentage: float
    actual_count: int | None
    actual_capacity_percentage: float | None
    attendance_percentage: float | None
    difference: int | None


class AttendanceHistoryPoint(TypedDict):
    session_date: str
    planned_count: int
    actual_count: int


def get_weekly_occupancy_comparison(
    database: DataBase,
    installation_id: int,
    week_start: date,
) -> list[SessionComparison]:
    if type(installation_id) is not int or installation_id <= 0:
        raise ValueError("El identificador del espacio debe ser un entero positivo.")
    if week_start.weekday() != 0:
        raise ValueError("La semana debe comenzar en lunes.")

    installation = database.executeQuery(
        "SELECT id FROM installation WHERE id = ?",
        installation_id,
    )
    if not installation:
        raise ValueError("No existe el espacio seleccionado.")

    week_end = week_start + timedelta(days=6)
    activities = database.executeQuery(
        """
        SELECT
            activity.id,
            activity.category,
            activity.level,
            activity.start_date,
            activity.start_time,
            activity.end_time,
            activity.available_places,
            activity_day.weekday
        FROM activity
        JOIN activity_day ON activity_day.activity_id = activity.id
        WHERE activity.installation_id = ?
        ORDER BY activity.id
        """,
        installation_id,
    )
    confirmed_counts = {
        int(row["activity_id"]): int(row["planned_count"])
        for row in database.executeQuery(
            """
            SELECT inscripcion.activity_id, COUNT(*) AS planned_count
            FROM inscripcion
            JOIN activity ON activity.id = inscripcion.activity_id
            WHERE inscripcion.estado = 'confirmado'
              AND activity.installation_id = ?
            GROUP BY inscripcion.activity_id
            """,
            installation_id,
        )
    }
    recorded_sessions = {
        (int(row["activity_id"]), str(row["session_date"])): {
            "planned_count": int(row["planned_count"]),
            "actual_count": int(row["actual_count"]),
        }
        for row in database.executeQuery(
            """
            SELECT
                attendance_session.activity_id,
                attendance_session.session_date,
                attendance_session.planned_count,
                COUNT(
                    CASE WHEN attendance_record.attended = 1 THEN 1 END
                ) AS actual_count
            FROM attendance_session
            JOIN activity
                ON activity.id = attendance_session.activity_id
            LEFT JOIN attendance_record
                ON attendance_record.activity_id = attendance_session.activity_id
                AND attendance_record.session_date = attendance_session.session_date
            WHERE activity.installation_id = ?
              AND attendance_session.session_date BETWEEN ? AND ?
            GROUP BY
                attendance_session.activity_id,
                attendance_session.session_date,
                attendance_session.planned_count
            """,
            installation_id,
            week_start.isoformat(),
            week_end.isoformat(),
        )
    }

    result: list[SessionComparison] = []
    for day_offset in range(7):
        session_date = week_start + timedelta(days=day_offset)
        weekday = WEEKDAYS[session_date.weekday()]
        for activity in activities:
            activity_start_date = activity["start_date"]
            if (
                activity["weekday"] != weekday
                or (
                    activity_start_date is not None
                    and str(activity_start_date) > session_date.isoformat()
                )
            ):
                continue

            activity_id = int(activity["id"])
            capacity = int(activity["available_places"])
            recorded = recorded_sessions.get((activity_id, session_date.isoformat()))
            planned_count = (
                recorded["planned_count"]
                if recorded is not None
                else confirmed_counts.get(activity_id, 0)
            )
            actual_count = (
                recorded["actual_count"] if recorded is not None else None
            )
            planned_percentage = round(planned_count / capacity * 100, 1)
            actual_percentage = (
                round(actual_count / capacity * 100, 1)
                if actual_count is not None
                else None
            )
            attendance_percentage = (
                round(actual_count / planned_count * 100, 1)
                if actual_count is not None and planned_count > 0
                else None
            )
            result.append(
                {
                    "activity_id": activity_id,
                    "activity": f"{activity['category']} - {activity['level']}",
                    "session_date": session_date.isoformat(),
                    "weekday": weekday,
                    "schedule": (
                        f"{activity['start_time']}-{activity['end_time']}"
                    ),
                    "planned_count": planned_count,
                    "capacity": capacity,
                    "planned_capacity_percentage": planned_percentage,
                    "actual_count": actual_count,
                    "actual_capacity_percentage": actual_percentage,
                    "attendance_percentage": attendance_percentage,
                    "difference": (
                        actual_count - planned_count
                        if actual_count is not None
                        else None
                    ),
                }
            )

    return result


def get_activity_attendance_history(
    database: DataBase,
    activity_id: int,
    through_date: date,
) -> list[AttendanceHistoryPoint]:
    activity = database.executeQuery(
        "SELECT id FROM activity WHERE id = ?",
        activity_id,
    )
    if not activity:
        raise ValueError("No existe la actividad seleccionada.")

    rows = database.executeQuery(
        """
        SELECT
            attendance_session.session_date,
            attendance_session.planned_count,
            COUNT(
                CASE WHEN attendance_record.attended = 1 THEN 1 END
            ) AS actual_count
        FROM attendance_session
        LEFT JOIN attendance_record
            ON attendance_record.activity_id = attendance_session.activity_id
            AND attendance_record.session_date = attendance_session.session_date
        WHERE attendance_session.activity_id = ?
          AND attendance_session.session_date <= ?
        GROUP BY
            attendance_session.session_date,
            attendance_session.planned_count
        ORDER BY attendance_session.session_date
        """,
        activity_id,
        through_date.isoformat(),
    )
    return [
        {
            "session_date": str(row["session_date"]),
            "planned_count": int(row["planned_count"]),
            "actual_count": int(row["actual_count"]),
        }
        for row in rows
    ]


def attendance_chart_lines(
    history: list[AttendanceHistoryPoint],
) -> list[str]:
    if not history:
        return ["No hay asistencia registrada para esta actividad."]

    max_count = max(
        max(point["planned_count"], point["actual_count"])
        for point in history
    )
    chart_scale = max(max_count, 1)
    lines = ["Evolución: planificada (#) frente a asistencia real (*)"]
    for point in history:
        planned_size = round(point["planned_count"] / chart_scale * 20)
        actual_size = round(point["actual_count"] / chart_scale * 20)
        if point["planned_count"] and planned_size == 0:
            planned_size = 1
        if point["actual_count"] and actual_size == 0:
            actual_size = 1
        lines.append(
            f"{point['session_date']} | P [{'#' * planned_size}] "
            f"{point['planned_count']} | R [{'*' * actual_size}] "
            f"{point['actual_count']}"
        )
    return lines


def iniciar_consulta_ocupacion_real(database: DataBase) -> None:
    installations = database.executeQuery(
        "SELECT id, name FROM installation ORDER BY name"
    )
    if not installations:
        print("No hay espacios disponibles para consultar.")
        return

    print_table(
        "ESPACIOS DISPONIBLES",
        ["ID", "Espacio"],
        [[installation["id"], installation["name"]] for installation in installations],
    )
    installation_ids = {int(installation["id"]) for installation in installations}
    while True:
        try:
            installation_id = int(input("Selecciona el ID del espacio: ").strip())
        except ValueError:
            print("El ID del espacio debe ser numérico.")
            continue
        if installation_id in installation_ids:
            break
        print("No existe un espacio con ese ID.")

    week_start = _select_week_start(date.today())
    if week_start is None:
        return

    comparisons = get_weekly_occupancy_comparison(
        database,
        installation_id,
        week_start,
    )
    print_weekly_occupancy_comparison(comparisons, week_start)
    if not comparisons:
        return

    activities = {
        comparison["activity_id"]: comparison["activity"]
        for comparison in comparisons
    }
    print_table(
        "ACTIVIDADES DE LA SEMANA",
        ["ID", "Actividad"],
        [[activity_id, name] for activity_id, name in activities.items()],
    )
    while True:
        selection = input(
            "ID de actividad para ver la gráfica (0 para salir): "
        ).strip()
        if selection == "0":
            return
        try:
            activity_id = int(selection)
        except ValueError:
            print("El ID de actividad debe ser numérico.")
            continue
        if activity_id in activities:
            break
        print("Selecciona un ID de actividad de la lista.")

    week_end = week_start + timedelta(days=6)
    history = get_activity_attendance_history(database, activity_id, week_end)
    print_table(
        f"ASISTENCIA - {activities[activity_id]}",
        ["Gráfica"],
        [[line] for line in attendance_chart_lines(history)],
    )


def print_weekly_occupancy_comparison(
    comparisons: list[SessionComparison],
    week_start: date,
) -> None:
    if not comparisons:
        print(
            f"No hay actividades programadas en este espacio durante la semana "
            f"del {week_start.isoformat()}."
        )
        return

    print_table(
        f"PLANIFICADA Y REAL - SEMANA DEL {week_start.isoformat()}",
        [
            "Fecha",
            "Día",
            "Actividad",
            "Horario",
            "Planificada",
            "Real",
            "Real / planificada",
            "Diferencia",
        ],
        [
            [
                comparison["session_date"],
                comparison["weekday"],
                f"{comparison['activity']} (ID {comparison['activity_id']})",
                comparison["schedule"],
                (
                    f"{comparison['planned_count']}/{comparison['capacity']} "
                    f"({comparison['planned_capacity_percentage']:.1f}%)"
                ),
                (
                    "Pendiente"
                    if comparison["actual_count"] is None
                    else (
                        f"{comparison['actual_count']}/{comparison['capacity']} "
                        f"({comparison['actual_capacity_percentage']:.1f}%)"
                    )
                ),
                (
                    "Pendiente"
                    if comparison["actual_count"] is None
                    else (
                        "N/D"
                        if comparison["attendance_percentage"] is None
                        else f"{comparison['attendance_percentage']:.1f}%"
                    )
                ),
                (
                    "Pendiente"
                    if comparison["difference"] is None
                    else f"{comparison['difference']:+d}"
                ),
            ]
            for comparison in comparisons
        ],
    )


def _select_week_start(today: date) -> date | None:
    selected_week = today - timedelta(days=today.weekday())
    while True:
        week_end = selected_week + timedelta(days=6)
        selection = input(
            f"Semana {selected_week.isoformat()} - {week_end.isoformat()} "
            "(A: anterior, Enter: consultar, Q: salir): "
        ).strip().lower()
        if selection in {"a", "←"}:
            selected_week -= timedelta(days=7)
        elif selection in {"", "q"}:
            return selected_week if selection == "" else None
        else:
            print(
                "Usa A para ir a la semana anterior, Enter para consultar "
                "o Q para salir."
            )
