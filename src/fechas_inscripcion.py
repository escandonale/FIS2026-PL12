from datetime import date

from src.util.database import DataBase


def migrate_registration_dates(database: DataBase) -> None:
    columns = database.executeQuery("PRAGMA table_info(activity)")
    existing_columns = {column["name"] for column in columns}
    registration_columns = {
        "start_date": "TEXT",
        "member_registration_start": "TEXT",
        "member_registration_end": "TEXT",
        "non_member_registration_start": "TEXT",
        "non_member_registration_end": "TEXT",
    }

    for column, column_type in registration_columns.items():
        if column not in existing_columns:
            database.executeUpdateQuery(
                f"ALTER TABLE activity ADD COLUMN {column} {column_type}"
            )


def get_actividades_no_iniciadas(
    database: DataBase, today: date | None = None
) -> list[dict[str, object]]:
    current_date = (today or date.today()).isoformat()
    return database.executeQuery(
        """
        SELECT activity.id, activity.category, activity.level,
               activity.start_date, installation.name AS installation
        FROM activity
        LEFT JOIN installation ON installation.id = activity.installation_id
        WHERE activity.start_date > ?
        ORDER BY activity.start_date, activity.id
        """,
        current_date,
    )


def abrir_plazo_inscripcion(
    database: DataBase,
    activity_id: int,
    member_start: str,
    member_end: str,
    non_member_start: str,
    non_member_end: str,
    today: date | None = None,
) -> dict[str, object]:
    if type(activity_id) is not int or activity_id <= 0:
        raise ValueError("Selecciona un ID de actividad válido.")

    current_date = today or date.today()
    member_start_date = _parse_iso_date(member_start, "inicio para socios")
    member_end_date = _parse_iso_date(member_end, "fin para socios")
    non_member_start_date = _parse_iso_date(
        non_member_start, "inicio para no socios"
    )
    non_member_end_date = _parse_iso_date(non_member_end, "fin para no socios")

    if any(
        registration_date < current_date
        for registration_date in (
            member_start_date,
            member_end_date,
            non_member_start_date,
            non_member_end_date,
        )
    ):
        raise ValueError(
            "Ninguna fecha de inscripción puede ser anterior a la fecha actual."
        )
    if member_end_date <= member_start_date:
        raise ValueError(
            "El fin del plazo para socios debe ser posterior a su inicio."
        )
    if non_member_start_date <= member_end_date:
        raise ValueError(
            "El plazo para no socios debe empezar después de que termine el de socios."
        )
    if non_member_end_date <= non_member_start_date:
        raise ValueError(
            "El fin del plazo para no socios debe ser posterior a su inicio."
        )

    activities = database.executeQuery(
        "SELECT id, start_date FROM activity WHERE id = ?",
        activity_id,
    )
    if not activities:
        raise ValueError("No existe una actividad con ese ID.")
    activity_start_value = activities[0]["start_date"]
    if not isinstance(activity_start_value, str):
        raise ValueError("La actividad no tiene una fecha de inicio asignada.")
    activity_start = _parse_iso_date(
        activity_start_value, "inicio de la actividad"
    )
    if activity_start <= current_date:
        raise ValueError("La actividad ya ha comenzado o comienza hoy.")

    if any(
        registration_date >= activity_start
        for registration_date in (
            member_start_date,
            member_end_date,
            non_member_start_date,
            non_member_end_date,
        )
    ):
        raise ValueError(
            "Todos los plazos de inscripción deben terminar antes del inicio "
            "de la actividad."
        )

    database.executeUpdateQuery(
        """
        UPDATE activity
        SET member_registration_start = ?,
            member_registration_end = ?,
            non_member_registration_start = ?,
            non_member_registration_end = ?
        WHERE id = ?
        """,
        member_start_date.isoformat(),
        member_end_date.isoformat(),
        non_member_start_date.isoformat(),
        non_member_end_date.isoformat(),
        activity_id,
    )
    return {
        "activity_id": activity_id,
        "start_date": activity_start.isoformat(),
        "member_registration_start": member_start_date.isoformat(),
        "member_registration_end": member_end_date.isoformat(),
        "non_member_registration_start": non_member_start_date.isoformat(),
        "non_member_registration_end": non_member_end_date.isoformat(),
    }


def _parse_iso_date(value: str, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"La fecha de {field} debe tener el formato AAAA-MM-DD.")
    try:
        parsed_date = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"La fecha de {field} debe tener el formato AAAA-MM-DD."
        ) from None
    if parsed_date.isoformat() != value:
        raise ValueError(f"La fecha de {field} debe tener el formato AAAA-MM-DD.")
    return parsed_date