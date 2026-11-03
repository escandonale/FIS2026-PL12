from datetime import date

from src.util.database import DataBase


REGISTRATION_DATE_COLUMNS = (
    "member_registration_start",
    "member_registration_end",
    "non_member_registration_start",
    "non_member_registration_end",
)


def migrate_registration_dates(database: DataBase) -> None:
    columns = database.executeQuery("PRAGMA table_info(activity)")
    existing_columns = {column["name"] for column in columns}

    if "start_date" not in existing_columns:
        database.executeUpdateQuery("ALTER TABLE activity ADD COLUMN start_date TEXT")
        existing_columns.add("start_date")
    if "start_time" in existing_columns:
        database.executeUpdateQuery(
            """
            UPDATE activity
            SET start_date = substr(start_time, 1, 10)
            WHERE start_date IS NULL
              AND instr(start_time, '-') > 0
              AND length(start_time) >= 16
            """
        )
        database.executeUpdateQuery(
            """
            UPDATE activity
            SET start_time = substr(start_time, 12, 5)
            WHERE instr(start_time, '-') > 0
              AND length(start_time) >= 16
            """
        )

    legacy_columns = {
        "member_registration_start": "ini_socio",
        "member_registration_end": "fin_socio",
        "non_member_registration_start": "ini_no_socio",
        "non_member_registration_end": "fin_no_socio",
    }
    for column_name in REGISTRATION_DATE_COLUMNS:
        if column_name not in existing_columns:
            database.executeUpdateQuery(
                f"ALTER TABLE activity ADD COLUMN {column_name} TEXT"
            )
            existing_columns.add(column_name)
        legacy_name = legacy_columns[column_name]
        if legacy_name in existing_columns:
            database.executeUpdateQuery(
                f"""
                UPDATE activity
                SET {column_name} = substr({legacy_name}, 1, 10)
                WHERE {column_name} IS NULL AND {legacy_name} IS NOT NULL
                """
            )


def get_actividades_no_iniciadas(
    database: DataBase, today: date | None = None
) -> list[dict[str, object]]:
    current_date = today or date.today()
    return database.executeQuery(
        """
        SELECT id, category, level, start_date
        FROM activity
        WHERE start_date IS NOT NULL AND start_date > ?
        ORDER BY start_date, id
        """,
        current_date.isoformat(),
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
    current_date = today or date.today()
    activity = database.executeQuery(
        "SELECT start_date FROM activity WHERE id = ?",
        activity_id,
    )
    if not activity:
        raise ValueError("No existe una actividad con ese identificador.")

    parsed_member_start = _parse_date(member_start, "apertura de socios")
    parsed_member_end = _parse_date(member_end, "cierre de socios")
    parsed_non_member_start = _parse_date(
        non_member_start, "apertura de no socios"
    )
    parsed_non_member_end = _parse_date(non_member_end, "cierre de no socios")
    activity_start = _parse_date(activity[0]["start_date"], "inicio de actividad")

    if activity_start <= current_date:
        raise ValueError("La actividad ya ha comenzado.")
    if parsed_member_start < current_date or parsed_non_member_start < current_date:
        raise ValueError("La fecha de apertura no puede ser anterior a la fecha actual.")
    if parsed_member_end <= parsed_member_start:
        raise ValueError("El cierre de socios debe ser posterior a su apertura.")
    if parsed_non_member_end <= parsed_non_member_start:
        raise ValueError(
            "El cierre de no socios debe ser posterior a su apertura."
        )
    if parsed_non_member_start <= parsed_member_end:
        raise ValueError(
            "El plazo de no socios debe comenzar después del plazo de socios."
        )
    if (
        parsed_member_end >= activity_start
        or parsed_non_member_end >= activity_start
    ):
        raise ValueError(
            "Los plazos de inscripción deben finalizar antes de que comience la actividad."
        )
    date_values = (
        member_start,
        member_end,
        non_member_start,
        non_member_end,
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
        *date_values,
        activity_id,
    )
    return {
        "activity_id": activity_id,
        "member_registration_start": member_start,
        "member_registration_end": member_end,
        "non_member_registration_start": non_member_start,
        "non_member_registration_end": non_member_end,
    }


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"El formato de {field} debe ser AAAA-MM-DD.")
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"El formato de {field} debe ser AAAA-MM-DD.") from None
    if parsed_date.isoformat() != value:
        raise ValueError(f"El formato de {field} debe ser AAAA-MM-DD.")
    return parsed_date
