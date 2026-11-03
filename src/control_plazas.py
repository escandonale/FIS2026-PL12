from pathlib import Path

from src.activities import list_activities, migrate_activity_installation
from src.config import DATABASE, SCHEMA
from src.fechas_inscripcion import migrate_registration_dates
from src.util.database import DataBase


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

    activities = list_activities(database)
    if not activities:
        print("Todavía no hay actividades disponibles.")
        return

    print("\nACTIVIDADES DISPONIBLES")
    for activity in activities:
        print(
            f"[{activity['id']}] {activity['category']} - "
            f"{activity['level']} ({activity['installation']})"
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

    print("\nOCUPACIÓN DE LA ACTIVIDAD")
    print(f"Instalación: {report['installation'] or 'Sin asignar'}")
    print(f"Aforo máximo: {report['aforo_max']}")
    print(f"Plazas ocupadas: {report['plazas_ocupadas']}")
    print(f"Plazas libres: {report['plazas_libres']}")

    print("\nPERSONAS INSCRITAS")
    registrations = report["inscripciones"]
    if not registrations:
        print("No hay personas inscritas en esta actividad.")
        return

    print("Nombre | Apellidos | Socio | Fecha de inscripción | Estado")
    for registration in registrations:
        member = "Sí" if registration["es_socio"] else "No"
        status = (
            "Inscrito"
            if registration["estado"] == "confirmado"
            else "Lista de espera"
        )
        print(
            f"{registration['nombre']} | {registration['apellidos']} | "
            f"{member} | {registration['fecha_inscripcion']} | {status}"
        )


if __name__ == "__main__":
    control_plazas()
