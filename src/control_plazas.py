from pathlib import Path

from src.activities import list_activities, migrate_activity_installation
from src.actividades.actividades_modelo import migrate_cancellation_status
from src.config import DATABASE, SCHEMA
from src.fechas_inscripcion import migrate_registration_dates
from src.util.database import DataBase
from src.util.pretty_tables import print_table
from src.util.unexpectedException import UnexpectedException


def conectar_bd(db_name: str | Path = DATABASE) -> DataBase:
    return DataBase(db_name)


def get_activity_seat_report(
    database: DataBase, activity_id: int
) -> dict[str, object] | None:
    activities = database.executeQuery(
        """
        SELECT
            activity.id,
            installation.name AS installation,
            activity.available_places AS aforo_max,
            COUNT(
                CASE WHEN inscripcion.estado = 'confirmado' THEN 1 END
            ) AS plazas_ocupadas
        FROM activity
        LEFT JOIN installation ON installation.id = activity.installation_id
        LEFT JOIN inscripcion ON inscripcion.activity_id = activity.id
        WHERE activity.id = ?
        GROUP BY activity.id, installation.name, activity.available_places
        """,
        activity_id,
    )
    if not activities:
        return None

    registrations = database.executeQuery(
        """
        SELECT nombre, apellidos, es_socio, fecha_inscripcion, estado
        FROM inscripcion
        WHERE activity_id = ?
        ORDER BY apellidos COLLATE NOCASE, nombre COLLATE NOCASE, id
        """,
        activity_id,
    )
    summary = activities[0]
    capacity = int(summary["aforo_max"])
    occupied = int(summary["plazas_ocupadas"])
    return {
        "id": summary["id"],
        "installation": summary["installation"],
        "aforo_max": capacity,
        "plazas_ocupadas": occupied,
        "plazas_libres": capacity - occupied,
        "inscripciones": registrations,
    }


def control_plazas(database: DataBase | None = None) -> None:
    if database is None:
        database = conectar_bd()
        database.executeScript(SCHEMA)
        migrate_registration_dates(database)
        migrate_activity_installation(database)
        migrate_cancellation_status(database)

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
                activity["installation"] or "Sin asignar",
            ]
            for activity in activities
        ],
    )

    while True:
        selection = input("\nIntroduce el ID de la actividad: ").strip()
        try:
            activity_id = int(selection)
        except ValueError:
            print("Introduce un ID válido.")
            continue

        report = get_activity_seat_report(database, activity_id)
        if report is None:
            print("No existe una actividad con ese ID.")
            continue
        break

    print_table(
        "OCUPACIÓN DE LA ACTIVIDAD",
        ["Instalación", "Aforo máximo", "Plazas ocupadas", "Plazas libres"],
        [[
            report["installation"] or "Sin asignar",
            report["aforo_max"],
            report["plazas_ocupadas"],
            report["plazas_libres"],
        ]],
    )

    registrations = report["inscripciones"]
    if not registrations:
        print("No hay personas inscritas en esta actividad.")
        return

    print_table(
        "PERSONAS INSCRITAS",
        ["Nombre", "Apellidos", "Socio", "Fecha de inscripción", "Estado"],
        [
            [
                registration["nombre"],
                registration["apellidos"],
                "Sí" if registration["es_socio"] else "No",
                registration["fecha_inscripcion"],
                (
                    "Inscrito"
                    if registration["estado"] == "confirmado"
                    else (
                        "Lista de espera"
                        if registration["estado"] == "lista de espera"
                        else "Cancelada"
                    )
                ),
            ]
            for registration in registrations
        ],
    )

