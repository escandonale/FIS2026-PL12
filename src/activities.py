from datetime import time
from enum import Enum
from typing import Iterable

from src.util.database import DataBase


class ActivityCategory(str, Enum):
    SWIMMING = "Natación"
    PILATES = "Pilates"
    FITNESS = "Acondicionamiento Físico"
    PADEL = "Padel"
    TENNIS = "Tenis"


class ActivityLevel(str, Enum):
    BEGINNER = "Iniciación"
    INTERMEDIATE = "Medio"
    ADVANCED = "Avanzado"


class Weekday(str, Enum):
    MONDAY = "Lunes"
    TUESDAY = "Martes"
    WEDNESDAY = "Miércoles"
    THURSDAY = "Jueves"
    FRIDAY = "Viernes"
    SATURDAY = "Sábado"
    SUNDAY = "Domingo"


WEEKDAYS = tuple(Weekday)


class RegistrationsAlreadyOpenError(RuntimeError):
    """Raised when an activity is added after registrations have opened."""


def add_activity(
    database: DataBase,
    category: ActivityCategory | str,
    level: ActivityLevel | str,
    weekdays: Iterable[Weekday | str],
    start_time: str,
    end_time: str,
    available_places: int,
    installation_id: int,
) -> dict[str, object]:
    category = _parse_enum(ActivityCategory, category, "categoría")
    level = _parse_enum(ActivityLevel, level, "nivel")
    parsed_weekdays = _parse_weekdays(weekdays)
    validate_times(start_time, end_time)
    if type(available_places) is not int or available_places <= 0:
        raise ValueError("El número de plazas debe ser un entero mayor que cero.")
    if type(installation_id) is not int:
        raise ValueError("Selecciona una instalación válida.")

    installation = database.executeQuery(
        """
        SELECT installation.id, installation.name
        FROM installation
        JOIN category_installation
            ON installation.id = category_installation.installation_id
        WHERE installation.id = ? AND category_installation.category = ?
        """,
        installation_id,
        category.value,
    )
    if not installation:
        raise ValueError(
            f"La instalación seleccionada no está adaptada para {category.value}."
        )

    activity_id = database.executeTransaction(
        """
        INSERT INTO activity (
            category, level, installation_id, start_time, end_time, available_places
        )
        SELECT ?, ?, ?, ?, ?, ?
        WHERE EXISTS (
            SELECT 1
            FROM offer
            WHERE id = 1 AND registrations_open = 0
        )
        AND EXISTS (
            SELECT 1
            FROM category_installation
            WHERE category = ? AND installation_id = ?
        )
        """,
        (
            category.value,
            level.value,
            installation_id,
            start_time,
            end_time,
            available_places,
            category.value,
            installation_id,
        ),
        "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
        [(weekday.value,) for weekday in parsed_weekdays],
    )
    if activity_id is None:
        offer = database.executeQuery(
            "SELECT registrations_open FROM offer WHERE id = 1"
        )
        if not offer:
            raise RuntimeError("No se ha inicializado la oferta de actividades.")
        if offer[0]["registrations_open"]:
            raise RegistrationsAlreadyOpenError(
                "No se puede añadir una actividad después de abrir las inscripciones."
            )
        raise RuntimeError("No se pudo registrar la actividad.")

    return {
        "id": activity_id,
        "category": category.value,
        "level": level.value,
        "installation": installation[0]["name"],
        "weekdays": [weekday.value for weekday in parsed_weekdays],
        "start_time": start_time,
        "end_time": end_time,
        "available_places": available_places,
    }


def get_activity(database: DataBase, activity_id: int) -> dict[str, object] | None:
    activities = database.executeQuery(
        """
        SELECT activity.id, activity.category, activity.level,
               installation.name AS installation,
               activity.start_time, activity.end_time, activity.available_places
        FROM activity
        LEFT JOIN installation ON activity.installation_id = installation.id
        WHERE activity.id = ?
        """,
        activity_id,
    )
    if not activities:
        return None

    day_rows = database.executeQuery(
        "SELECT weekday FROM activity_day WHERE activity_id = ?",
        activity_id,
    )
    weekday_values = {row["weekday"] for row in day_rows}
    activity = activities[0]
    return {
        "id": activity["id"],
        "category": activity["category"],
        "level": activity["level"],
        "installation": activity["installation"],
        "weekdays": [
            weekday.value
            for weekday in WEEKDAYS
            if weekday.value in weekday_values
        ],
        "start_time": activity["start_time"],
        "end_time": activity["end_time"],
        "available_places": activity["available_places"],
    }


def list_activities(database: DataBase) -> list[dict[str, object]]:
    rows = database.executeQuery(
        """
        SELECT
            activity.id,
            activity.category,
            activity.level,
            installation.name AS installation,
            activity.start_time,
            activity.end_time,
            activity.available_places,
            activity_day.weekday
        FROM activity
        LEFT JOIN installation ON activity.installation_id = installation.id
        LEFT JOIN activity_day ON activity.id = activity_day.activity_id
        ORDER BY
            activity.id,
            CASE activity_day.weekday
                WHEN 'Lunes' THEN 1
                WHEN 'Martes' THEN 2
                WHEN 'Miércoles' THEN 3
                WHEN 'Jueves' THEN 4
                WHEN 'Viernes' THEN 5
                WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7
            END
        """
    )

    activities = []
    for row in rows:
        if not activities or activities[-1]["id"] != row["id"]:
            activities.append({
                "id": row["id"],
                "category": row["category"],
                "level": row["level"],
                "installation": row["installation"],
                "weekdays": [],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "available_places": row["available_places"],
            })
        if row["weekday"] is not None:
            activities[-1]["weekdays"].append(row["weekday"])

    return activities


def get_installations(
    database: DataBase, category: ActivityCategory | str
) -> list[dict[str, object]]:
    category = _parse_enum(ActivityCategory, category, "categoría")
    return database.executeQuery(
        """
        SELECT installation.id, installation.name
        FROM installation
        JOIN category_installation
            ON installation.id = category_installation.installation_id
        WHERE category_installation.category = ?
        ORDER BY installation.id
        """,
        category.value,
    )


def migrate_activity_installation(database: DataBase) -> None:
    columns = database.executeQuery("PRAGMA table_info(activity)")
    if not any(column["name"] == "installation_id" for column in columns):
        database.executeUpdateQuery(
            "ALTER TABLE activity ADD COLUMN installation_id "
            "INTEGER REFERENCES installation (id)"
        )


def _parse_enum(enum_type: type[Enum], value: Enum | str, field: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        options = ", ".join(member.value for member in enum_type)
        raise ValueError(
            f"{field.capitalize()} no válida. Opciones: {options}."
        ) from None


def _parse_weekdays(weekdays: Iterable[Weekday | str]) -> tuple[Weekday, ...]:
    if isinstance(weekdays, (str, bytes)):
        raise ValueError("Selecciona uno o varios días de la semana.")

    parsed = {_parse_enum(Weekday, weekday, "día") for weekday in weekdays}
    if not parsed:
        raise ValueError("Selecciona al menos un día de la semana.")
    return tuple(weekday for weekday in WEEKDAYS if weekday in parsed)


def validate_times(start_time: str, end_time: str) -> None:
    try:
        parsed_start = time.fromisoformat(start_time)
        parsed_end = time.fromisoformat(end_time)
    except (TypeError, ValueError):
        raise ValueError("Las horas deben tener el formato HH:MM.") from None

    if parsed_start.strftime("%H:%M") != start_time:
        raise ValueError("La hora de inicio debe tener el formato HH:MM.")
    if parsed_end.strftime("%H:%M") != end_time:
        raise ValueError("La hora de fin debe tener el formato HH:MM.")
    if parsed_end <= parsed_start:
        raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")
