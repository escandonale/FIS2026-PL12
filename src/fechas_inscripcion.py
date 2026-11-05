from datetime import date

from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


REGISTRATION_DATE_COLUMNS = (
    "member_registration_start",
    "member_registration_end",
    "non_member_registration_start",
    "non_member_registration_end",
)


def migrate_registration_dates(database: DataBase) -> None:
    database.executeScriptFromString(
        """
        CREATE TABLE IF NOT EXISTS offer (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            registrations_open INTEGER NOT NULL DEFAULT 0
                CHECK (registrations_open IN (0, 1))
        );
        INSERT OR IGNORE INTO offer (id, registrations_open) VALUES (1, 0);
        """
    )
    offer_columns = {
        column["name"] for column in database.executeQuery("PRAGMA table_info(offer)")
    }
    offer_fields = {
        "member_registration_start": "TEXT",
        "member_registration_end": "TEXT",
        "non_member_registration_start": "TEXT",
        "non_member_registration_end": "TEXT",
        "member_registration_status": (
            "TEXT NOT NULL DEFAULT 'scheduled' "
            "CHECK (member_registration_status IN ('scheduled', 'open', 'closed'))"
        ),
        "non_member_registration_status": (
            "TEXT NOT NULL DEFAULT 'scheduled' "
            "CHECK (non_member_registration_status IN ('scheduled', 'open', 'closed'))"
        ),
    }
    for column_name, column_definition in offer_fields.items():
        if column_name not in offer_columns:
            database.executeUpdateQuery(
                f"ALTER TABLE offer ADD COLUMN {column_name} {column_definition}"
            )

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

    activity_count = database.executeQuery(
        "SELECT COUNT(*) AS count FROM activity"
    )[0]["count"]
    offer = database.executeQuery(
        """
        SELECT member_registration_start, member_registration_end,
               non_member_registration_start, non_member_registration_end
        FROM offer WHERE id = 1
        """
    )
    if activity_count and offer and all(
        offer[0][column_name] is None for column_name in REGISTRATION_DATE_COLUMNS
    ):
        legacy_periods = database.executeQuery(
            """
            SELECT
                MIN(member_registration_start) AS member_registration_start,
                MAX(member_registration_end) AS member_registration_end,
                MIN(non_member_registration_start) AS non_member_registration_start,
                MAX(non_member_registration_end) AS non_member_registration_end
            FROM activity
            """
        )[0]
        if any(value is not None for value in legacy_periods.values()):
            database.executeUpdateQuery(
                """
                UPDATE offer
                SET member_registration_start = ?,
                    member_registration_end = ?,
                    non_member_registration_start = ?,
                    non_member_registration_end = ?
                WHERE id = 1
                """,
                *(
                    legacy_periods[column_name]
                    for column_name in REGISTRATION_DATE_COLUMNS
                ),
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
    if activity[0]["start_date"] is None:
        raise ValueError("La actividad no tiene fecha de inicio asignada.")

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
    configurar_inscripciones(
        database,
        member_action="schedule",
        member_start=member_start,
        member_end=member_end,
        non_member_action="schedule",
        non_member_start=non_member_start,
        non_member_end=non_member_end,
        today=current_date,
    )
    return {
        "activity_id": activity_id,
        "member_registration_start": member_start,
        "member_registration_end": member_end,
        "non_member_registration_start": non_member_start,
        "non_member_registration_end": non_member_end,
    }


def configurar_inscripciones(
    database: DataBase,
    member_action: str,
    non_member_action: str,
    member_start: str | None = None,
    member_end: str | None = None,
    non_member_start: str | None = None,
    non_member_end: str | None = None,
    today: date | None = None,
) -> dict[str, object]:
    current_date = today or date.today()
    actions = {
        "socios": (
            member_action,
            "member_registration_start",
            "member_registration_end",
            "member_registration_status",
            member_start,
            member_end,
        ),
        "no socios": (
            non_member_action,
            "non_member_registration_start",
            "non_member_registration_end",
            "non_member_registration_status",
            non_member_start,
            non_member_end,
        ),
    }
    valid_actions = {"keep", "schedule", "open", "close"}
    if any(action not in valid_actions for action, *_ in actions.values()):
        raise ValueError("La acción debe ser keep, schedule, open o close.")

    current_offer = database.executeQuery(
        """
        SELECT member_registration_start, member_registration_end,
               member_registration_status,
               non_member_registration_start, non_member_registration_end,
               non_member_registration_status
        FROM offer WHERE id = 1
        """
    )
    if not current_offer:
        raise UnexpectedException("No se ha inicializado la oferta de actividades.")
    dates = dict(current_offer[0])

    for group, (
        action,
        start_column,
        end_column,
        _,
        start_value,
        end_value,
    ) in actions.items():
        if action != "schedule":
            if start_value is not None or end_value is not None:
                raise ValueError(
                    f"No se deben indicar fechas para la acción de {group}."
                )
            continue
        start_date = _parse_date(start_value, f"apertura de {group}")
        end_date = _parse_date(end_value, f"cierre de {group}")
        if start_date < current_date:
            raise ValueError("La fecha de apertura no puede ser anterior a hoy.")
        if end_date <= start_date:
            raise ValueError("La fecha de fin debe ser posterior a la de apertura.")
        dates[start_column] = start_date.isoformat()
        dates[end_column] = end_date.isoformat()

    member_end_date = _optional_date(dates["member_registration_end"])
    non_member_start_date = _optional_date(dates["non_member_registration_start"])
    if (
        member_end_date is not None
        and non_member_start_date is not None
        and non_member_start_date <= member_end_date
    ):
        raise ValueError(
            "El plazo de no socios debe comenzar después del plazo de socios."
        )

    activity_dates = database.executeQuery(
        "SELECT id, start_date FROM activity ORDER BY id"
    )
    for group, (
        action,
        _,
        end_column,
        _,
        *_,
    ) in actions.items():
        if action != "schedule":
            continue
        end_date = _optional_date(dates[end_column])
        for activity in activity_dates:
            if activity["start_date"] is None:
                raise ValueError(
                    "No se puede programar el plazo global: la actividad "
                    f"{activity['id']} no tiene fecha de inicio."
                )
            activity_start = _parse_date(
                activity["start_date"], "inicio de actividad"
            )
            if end_date is not None and end_date >= activity_start:
                raise ValueError(
                    f"El cierre para {group} debe ser anterior al inicio "
                    f"de la actividad {activity['id']}."
                )

    transaction: list[tuple[str, tuple[object, ...]]] = []
    for (
        action,
        start_column,
        end_column,
        status_column,
        start_value,
        _,
    ) in actions.values():
        if action == "schedule":
            transaction.append(
                (
                    f"""
                    UPDATE offer
                    SET {start_column} = ?, {end_column} = ?,
                        {status_column} = 'scheduled'
                    WHERE id = 1
                    """,
                    (
                        dates[start_column],
                        dates[end_column],
                    ),
                )
            )
        elif action in {"open", "close"}:
            status = "open" if action == "open" else "closed"
            transaction.append(
                (
                    f"UPDATE offer SET {status_column} = ? WHERE id = 1",
                    (status,),
                )
            )
        elif action == "keep":
            continue

    if transaction:
        for (
            action,
            start_column,
            end_column,
            _,
            *_,
        ) in actions.values():
            if action == "schedule":
                transaction.append(
                    (
                        f"""
                        UPDATE activity
                        SET {start_column} = ?, {end_column} = ?
                        """,
                        (dates[start_column], dates[end_column]),
                    )
                )
        transaction.append(
            (
                """
                UPDATE offer
                SET registrations_open = 1
                WHERE id = 1
                """,
                (),
            )
        )
        database.executeTransactionQueries(transaction)

    return {
        "member_registration_start": dates["member_registration_start"],
        "member_registration_end": dates["member_registration_end"],
        "member_registration_status": _effective_registration_status(
            "member",
            member_action,
            dates,
            current_date,
            current_offer[0]["member_registration_status"],
        ),
        "non_member_registration_start": dates["non_member_registration_start"],
        "non_member_registration_end": dates["non_member_registration_end"],
        "non_member_registration_status": _effective_registration_status(
            "non_member",
            non_member_action,
            dates,
            current_date,
            current_offer[0]["non_member_registration_status"],
        ),
    }


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    return _parse_date(value, "fecha de inscripción")


def _effective_registration_status(
    group: str,
    action: str,
    dates: dict[str, object],
    current_date: date,
    stored_status: str,
) -> str:
    if action == "open":
        return "open"
    if action == "close":
        return "closed"
    if action == "schedule":
        return "scheduled"
    if stored_status in {"open", "closed"}:
        return stored_status
    start_column = f"{group}_registration_start"
    end_column = f"{group}_registration_end"
    start_date = _optional_date(dates[start_column])
    end_date = _optional_date(dates[end_column])
    if start_date is not None and end_date is not None:
        if start_date <= current_date <= end_date:
            return "open"
        if current_date > end_date:
            return "closed"
    return "scheduled"


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
