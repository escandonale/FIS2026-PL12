from datetime import date, time
from enum import Enum
from typing import Iterable, TypedDict

from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


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


class Installation(TypedDict):
    id: int
    name: str


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
    installation_id: int | None = None,
    start_date: str | None = None,
) -> dict[str, object]:
    category = _parse_enum(ActivityCategory, category, "categoría")
    level = _parse_enum(ActivityLevel, level, "nivel")
    parsed_weekdays = _parse_weekdays(weekdays)
    validate_times(start_time, end_time)
    if start_date is not None:
        _parse_activity_date(start_date)
    if type(available_places) is not int or available_places <= 0:
        raise ValueError("El número de plazas debe ser un entero mayor que cero.")
    activity_id = database.executeTransaction(
        """
        INSERT INTO activity (
            category, level, installation_id, start_date, start_time, end_time,
            available_places
        )
        SELECT ?, ?, ?, ?, ?, ?, ?
        WHERE EXISTS (
            SELECT 1
            FROM offer
            WHERE id = 1 AND registrations_open = 0
        )
        """,
        (
            category.value,
            level.value,
            installation_id,
            start_date,
            start_time,
            end_time,
            available_places,
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
        "installation": None,
        "weekdays": [weekday.value for weekday in parsed_weekdays],
        "start_date": start_date,
        "start_time": start_time,
        "end_time": end_time,
        "available_places": available_places,
        "occupied_places": 0,
        "occupancy_percentage": 0.0,
    }


def get_activity(database: DataBase, activity_id: int) -> dict[str, object] | None:
    activities = database.executeQuery(
        """
        SELECT activity.id, activity.category, activity.level,
               installation.name AS installation,
               activity.start_date, activity.start_time, activity.end_time,
                  activity.available_places, activity.occupied_places,
                  activity.member_registration_start,
                  activity.member_registration_end,
                  activity.non_member_registration_start,
                  activity.non_member_registration_end
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
    activity_data = {
        "id": activity["id"],
        "category": activity["category"],
        "level": activity["level"],
        "installation": activity["installation"],
        "weekdays": [
            weekday.value
            for weekday in WEEKDAYS
            if weekday.value in weekday_values
        ],
        "start_date": activity["start_date"],
        "start_time": activity["start_time"],
        "end_time": activity["end_time"],
        "available_places": activity["available_places"],
        "occupied_places": activity["occupied_places"],
        "occupancy_percentage": round(
            activity["occupied_places"] / activity["available_places"] * 100,
            1,
        ),
    }
    date_fields = {
        column_name: activity[column_name]
        for column_name in (
            "member_registration_start",
            "member_registration_end",
            "non_member_registration_start",
            "non_member_registration_end",
        )
    }
    if any(value is not None for value in date_fields.values()):
        activity_data.update(date_fields)
    return activity_data


def assign_activity_to_installation(
    database: DataBase, activity_id: int, installation_id: int
) -> dict[str, object]:
    activity = database.executeQuery(
        "SELECT id, category FROM activity WHERE id = ?",
        activity_id,
    )
    if not activity:
        raise ValueError("No existe una actividad con ese identificador.")

    installation = database.executeQuery(
        """
        SELECT installation.id, installation.name
        FROM installation
        JOIN category_installation
            ON installation.id = category_installation.installation_id
        WHERE installation.id = ? AND category_installation.category = ?
        """,
        installation_id,
        activity[0]["category"],
    )
    if not installation:
        raise ValueError(
            "La instalación seleccionada no está adaptada para "
            f"{activity[0]['category']}."
        )

    conflicts = database.executeQuery(
        """
        SELECT other.id, other.start_time, other.end_time, other_day.weekday
        FROM activity AS current
        JOIN activity_day AS current_day
            ON current_day.activity_id = current.id
        JOIN activity AS other
            ON other.installation_id = ?
            AND other.id != current.id
        JOIN activity_day AS other_day
            ON other_day.activity_id = other.id
            AND other_day.weekday = current_day.weekday
        WHERE current.id = ?
          AND other.start_time < current.end_time
          AND other.end_time > current.start_time
        ORDER BY other_day.weekday, other.start_time
        """,
        installation_id,
        activity_id,
    )
    if conflicts:
        conflict = conflicts[0]
        raise ValueError(
            f"La instalación {installation[0]['name']} ya está ocupada el "
            f"{conflict['weekday']} por la actividad {conflict['id']} "
            f"({conflict['start_time']}-{conflict['end_time']})."
        )

    try:
        database.executeUpdateQuery(
            """
            UPDATE activity
            SET installation_id = ?
            WHERE id = ?
            """,
            installation_id,
            activity_id,
        )
    except UnexpectedException as error:
        if "schedule_conflict" in str(error):
            raise ValueError(
                f"La instalación {installation[0]['name']} tiene un solapamiento "
                "con otra actividad."
            ) from error
        raise
    return {
        "id": activity_id,
        "category": activity[0]["category"],
        "installation": installation[0]["name"],
    }


def set_activity_occupancy(
    database: DataBase, activity_id: int, occupied_places: int
) -> None:
    if type(occupied_places) is not int or occupied_places < 0:
        raise ValueError("La ocupación debe ser un entero no negativo.")

    activity = database.executeQuery(
        "SELECT available_places FROM activity WHERE id = ?",
        activity_id,
    )
    if not activity:
        raise ValueError("No existe una actividad con ese identificador.")
    if occupied_places > activity[0]["available_places"]:
        raise ValueError("La ocupación no puede superar la capacidad de la actividad.")

    database.executeUpdateQuery(
        "UPDATE activity SET occupied_places = ? WHERE id = ?",
        occupied_places,
        activity_id,
    )


def list_installation_conflicts(database: DataBase) -> list[dict[str, object]]:
    return database.executeQuery(
        """
        SELECT
            first_activity.id AS first_activity_id,
            second_activity.id AS second_activity_id,
            installation.name AS installation,
            first_day.weekday,
            first_activity.start_time AS first_start_time,
            first_activity.end_time AS first_end_time,
            second_activity.start_time AS second_start_time,
            second_activity.end_time AS second_end_time
        FROM activity AS first_activity
        JOIN activity_day AS first_day
            ON first_day.activity_id = first_activity.id
        JOIN activity AS second_activity
            ON second_activity.installation_id = first_activity.installation_id
            AND second_activity.id > first_activity.id
        JOIN activity_day AS second_day
            ON second_day.activity_id = second_activity.id
            AND second_day.weekday = first_day.weekday
        JOIN installation
            ON installation.id = first_activity.installation_id
        WHERE first_activity.start_time < second_activity.end_time
          AND first_activity.end_time > second_activity.start_time
        ORDER BY installation.name, first_day.weekday,
                 first_activity.start_time
        """
    )


def list_activities(database: DataBase) -> list[dict[str, object]]:
    rows = database.executeQuery(
        """
        SELECT
            activity.id,
            activity.category,
            activity.level,
            installation.name AS installation,
            activity.start_date,
            activity.start_time,
            activity.end_time,
            activity.available_places,
            activity.occupied_places,
            activity.member_registration_start,
            activity.member_registration_end,
            activity.non_member_registration_start,
            activity.non_member_registration_end,
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
            activity_data = {
                "id": row["id"],
                "category": row["category"],
                "level": row["level"],
                "installation": row["installation"],
                "weekdays": [],
                "start_date": row["start_date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "available_places": row["available_places"],
                "occupied_places": row["occupied_places"],
                "occupancy_percentage": round(
                    row["occupied_places"] / row["available_places"] * 100,
                    1,
                ),
            }
            date_fields = {
                column_name: row[column_name]
                for column_name in (
                    "member_registration_start",
                    "member_registration_end",
                    "non_member_registration_start",
                    "non_member_registration_end",
                )
            }
            if any(value is not None for value in date_fields.values()):
                activity_data.update(date_fields)
            activities.append(activity_data)
        if row["weekday"] is not None:
            activities[-1]["weekdays"].append(row["weekday"])

    return activities


def get_installations(
    database: DataBase, category: ActivityCategory | str
) -> list[Installation]:
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
    installation_column = next(
        (column for column in columns if column["name"] == "installation_id"),
        None,
    )
    occupied_places_column = next(
        (column for column in columns if column["name"] == "occupied_places"),
        None,
    )
    occupied_places_value = (
        "occupied_places" if occupied_places_column is not None else "0"
    )
    if installation_column is None or installation_column["notnull"]:
        installation_value = (
            "installation_id" if installation_column is not None else "NULL"
        )
        columns_by_name = {
            column["name"] for column in columns
        }
        preserved_columns = (
            "start_date",
            "member_registration_start",
            "member_registration_end",
            "non_member_registration_start",
            "non_member_registration_end",
        )
        preserved_values = {
            name: name if name in columns_by_name else "NULL"
            for name in preserved_columns
        }
        database.executeScriptFromString(
            f"""
            PRAGMA foreign_keys = OFF;
            BEGIN;
            CREATE TABLE activity_new (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL
                    CHECK (category IN (
                        'Natación', 'Pilates', 'Acondicionamiento Físico',
                        'Padel', 'Tenis'
                    )),
                level TEXT NOT NULL
                    CHECK (level IN ('Iniciación', 'Medio', 'Avanzado')),
                installation_id INTEGER,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                available_places INTEGER NOT NULL CHECK (available_places > 0),
                occupied_places INTEGER NOT NULL DEFAULT 0
                    CHECK (
                        occupied_places >= 0
                        AND occupied_places <= available_places
                    ),
                start_date TEXT,
                member_registration_start TEXT,
                member_registration_end TEXT,
                non_member_registration_start TEXT,
                non_member_registration_end TEXT,
                CHECK (end_time > start_time),
                FOREIGN KEY (category, installation_id)
                    REFERENCES category_installation (category, installation_id)
            );
            INSERT INTO activity_new (
                id, category, level, installation_id,
                start_time, end_time, available_places, occupied_places,
                start_date, member_registration_start, member_registration_end,
                non_member_registration_start, non_member_registration_end
            )
            SELECT
                id, category, level, {installation_value},
                start_time, end_time, available_places, {occupied_places_value},
                {preserved_values["start_date"]},
                {preserved_values["member_registration_start"]},
                {preserved_values["member_registration_end"]},
                {preserved_values["non_member_registration_start"]},
                {preserved_values["non_member_registration_end"]}
            FROM activity;
            DROP TABLE activity;
            ALTER TABLE activity_new RENAME TO activity;
            COMMIT;
            PRAGMA foreign_keys = ON;
            """
        )

    columns = database.executeQuery("PRAGMA table_info(activity)")
    if not any(column["name"] == "start_date" for column in columns):
        database.executeUpdateQuery("ALTER TABLE activity ADD COLUMN start_date TEXT")
        columns = database.executeQuery("PRAGMA table_info(activity)")

    for column_name in (
        "member_registration_start",
        "member_registration_end",
        "non_member_registration_start",
        "non_member_registration_end",
    ):
        if not any(column["name"] == column_name for column in columns):
            database.executeUpdateQuery(
                f"ALTER TABLE activity ADD COLUMN {column_name} TEXT"
            )
            columns = database.executeQuery("PRAGMA table_info(activity)")

    if not any(column["name"] == "occupied_places" for column in columns):
        database.executeUpdateQuery(
            """
            ALTER TABLE activity
            ADD COLUMN occupied_places INTEGER NOT NULL DEFAULT 0
                CHECK (occupied_places >= 0 AND occupied_places <= available_places)
            """
        )
        columns = database.executeQuery("PRAGMA table_info(activity)")

def _parse_activity_date(value: str) -> date:
    try:
        parsed_date = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(
            "La fecha de inicio debe tener el formato AAAA-MM-DD."
        ) from None
    if parsed_date.isoformat() != value:
        raise ValueError("La fecha de inicio debe tener el formato AAAA-MM-DD.")
    return parsed_date


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
