from datetime import date
from pathlib import Path

from src.activities import (
    ActivityCategory,
    ActivityLevel,
    Installation,
    RegistrationsAlreadyOpenError,
    Weekday,
    add_activity,
    assign_activity_to_installation,
    get_installations,
    list_installation_conflicts,
    list_activities,
    list_unassigned_activities,
    migrate_activity_installation,
    validate_times,
    validate_start_date,
)
from src.actividades.actividades_modelo import migrate_cancellation_status
from src.control_plazas import control_plazas
from src.config import CONSTRAINTS, DATA, DATABASE, SCHEMA
from src.actividades.actividades_vista import iniciar_cancelacion, iniciar_inscripcion
from src.asistencia import iniciar_registro_asistencia
from src.fechas_inscripcion import (
    configurar_inscripciones,
    migrate_registration_dates,
)
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


from src.usuarios.registro_usuarios_vista import (
    iniciar_registro_no_socio,
    iniciar_registro_socio,
)
from src.usuarios.registrar_usuarios import migrar_genero

def main() -> None:
    database_exists = Path(DATABASE).is_file()
    database = DataBase(DATABASE)
    try:
        database.executeScript(SCHEMA)
        migrar_genero(database)
        migrate_registration_dates(database)
        migrate_activity_installation(database)
        migrate_cancellation_status(database)
        database.executeScript(CONSTRAINTS)
        if not database_exists:
            # Comment this line to create an empty database instead.
            database.executeScript(DATA)
        run_menu(database)
    except UnexpectedException as error:
        print(f"Error al acceder a la base de datos: {error}")


def run_menu(database: DataBase) -> None:
    while True:
        conflicts = list_installation_conflicts(database)
        print("\nCENTRO DEPORTIVO")
        registration_state = database.executeQuery(
            """
            SELECT member_registration_status, non_member_registration_status
            FROM offer WHERE id = 1
            """
        )
        if not registration_state:
            raise UnexpectedException("No se ha inicializado la oferta de actividades.")
        member_status = registration_state[0]["member_registration_status"]
        non_member_status = registration_state[0]["non_member_registration_status"]
        state_label = (
            "ABIERTAS"
            if "open" in {member_status, non_member_status}
            else (
                "CERRADAS"
                if member_status == non_member_status == "closed"
                else "PROGRAMADAS"
            )
        )
        print(f"Inscripciones: {state_label}")
        if conflicts:
            display_existing_conflicts(database, conflicts)
            print("Las altas están bloqueadas hasta resolver los solapamientos.")
        else:
            print("1. Añadir actividad")
        print("2. Ver actividades")
        print("3. Asignar instalación")
        print("4. Gestionar inscripciones globales")
        print("5. Inscribir persona")
        print("6. Controlar plazas e inscripciones")
        print("7. Cancelar inscripción")
        print("8. Registrar nuevo usuario (no socio)")
        print("9. Registrar nuevo socio")
        print("10. Registrar asistencia")

        print("0. Salir")
        option = input("Selecciona una opción: ").strip()

        if option == "0":
            print("Hasta luego.")
            return
        if option == "1":
            if conflicts:
                print("No se pueden añadir actividades hasta resolver los solapamientos.")
                continue
            try:
                activity = create_activity_from_input(database)
                if activity is None:
                    continue
                print("\nActividad añadida correctamente:")
                print(f"Categoría: {activity['category']}")
                print(f"Nivel: {activity['level']}")
                installation = activity["installation"] or "Pendiente de asignación"
                print(f"Instalación: {installation}")
                print(f"Días: {', '.join(activity['weekdays'])}")
                print(
                    f"Horario: {activity['start_time']} - {activity['end_time']}"
                )
                print(f"Capacidad total: {activity['available_places']} plazas")
                print("Ocupación: 0% (0 plazas)")
            except ValueError as error:
                print(f"Datos no válidos: {error}")
            except RegistrationsAlreadyOpenError as error:
                print(error)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue

        if option == "2":
            try:
                activities = list_activities(database)
                if activities:
                    display_activities(activities)
                else:
                    print("Todavía no hay actividades en la oferta.")
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue

        if option == "3":
            try:
                _assign_installation_from_input(database)
            except ValueError as error:
                print(error)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue
        if option == "4":
            try:
                _open_registration_period_from_input(database)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue
        if option == "5":
            iniciar_inscripcion(database.dbname)
            continue
        if option == "6":
            try:
                control_plazas(database)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue
        if option == "7":
            iniciar_cancelacion(database.dbname)
            continue
        if option == "8":
            try:
                iniciar_registro_no_socio(database.dbname)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue
        if option == "9":
            try:
                iniciar_registro_socio(database.dbname)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue
        if option == "10":
            try:
                iniciar_registro_asistencia(database)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue

        print("Opción no válida. Elige 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 o 0.")


def display_activities(activities: list[dict[str, object]]) -> None:
    print("\nACTIVIDADES DISPONIBLES")
    for activity in activities:
        print(f"\nActividad {activity['id']}")
        print(f"Categoría: {activity['category']}")
        print(f"Nivel: {activity['level']}")
        print(f"Instalación: {activity['installation'] or 'Sin asignar'}")
        print(f"Días: {', '.join(activity['weekdays'])}")
        print(f"Fecha de inicio: {activity['start_date'] or 'Sin asignar'}")
        print(f"Horario: {activity['start_time']} - {activity['end_time']}")
        print(
            f"Ocupación: {activity['occupied_places']}/"
            f"{activity['available_places']} plazas "
            f"({activity['occupancy_percentage']}%)"
        )


def display_existing_conflicts(
    database: DataBase, conflicts: list[dict[str, object]] | None = None
) -> None:
    if conflicts is None:
        conflicts = list_installation_conflicts(database)
    if not conflicts:
        return

    print("\nAVISO: Se han encontrado solapamientos ya existentes:")
    for conflict in conflicts:
        print(
            f"- Actividades {conflict['first_activity_id']} y "
            f"{conflict['second_activity_id']} en {conflict['installation']}, "
            f"{conflict['weekday']}: "
            f"{conflict['first_start_time']}-{conflict['first_end_time']} y "
            f"{conflict['second_start_time']}-{conflict['second_end_time']}."
        )
    print("Usa «Asignar instalación a una actividad» para resolverlos.")


def create_activity_from_input(database: DataBase) -> dict[str, object] | None:
    category = _choose_option("Categoría", list(ActivityCategory))
    level = _choose_option("Nivel", list(ActivityLevel))
    weekdays = _choose_weekdays()
    while True:
        start_date = input(
            "Fecha de inicio de la actividad (AAAA-MM-DD): "
        ).strip()
        try:
            validate_start_date(start_date)
            break
        except ValueError as error:
            print(error)

    while True:
        start_time = input("Hora de inicio (HH:MM): ").strip()
        end_time = input("Hora de fin (HH:MM): ").strip()
        try:
            validate_times(start_time, end_time)
            break
        except ValueError as error:
            print(error)

    while True:
        places = input("Número de plazas: ").strip()
        try:
            available_places = int(places)
            if available_places <= 0:
                raise ValueError
            break
        except ValueError:
            print("El número de plazas debe ser un entero mayor que cero.")

    print("\nResumen de la actividad:")
    print(f"- Categoría: {category.value}")
    print(f"- Nivel: {level.value}")
    print(f"- Días: {', '.join(day.value for day in weekdays)}")
    print(f"- Fecha de inicio: {start_date}")
    print(f"- Horario: {start_time} - {end_time}")
    print(f"- Plazas: {available_places}")
    print("- Instalación: Sin asignar")
    answer = input("¿Guardar la actividad? (s/n): ").strip().lower()
    if answer not in {"s", "si", "sí"}:
        print("Creación cancelada.")
        return None

    return add_activity(
        database,
        category,
        level,
        weekdays,
        start_time,
        end_time,
        available_places,
        start_date=start_date,
    )


def _assign_installation_from_input(database: DataBase) -> None:
    activities = list_unassigned_activities(database)
    if not activities:
        print("Todavía no hay actividades pendientes de asignación.")
        return

    print("\nACTIVIDADES SIN ASIGNAR")
    for activity in activities:
        print(
            f"[{activity['id']}] {activity['category']} - "
            f"{activity['level']} | {', '.join(activity['weekdays'])} | "
            f"{activity['start_time']}-{activity['end_time']}"
        )

    selection = input("\nIntroduce el ID o nombre de la actividad: ").strip()
    activity = _find_activity_by_reference(activities, selection)
    if activity is None:
        print("No existe una actividad con ese identificador o nombre.")
        return

    installations = get_installations(database, activity["category"])
    if not installations:
        print("No hay instalaciones compatibles disponibles.")
        return
    installation = _choose_installation(installations)

    print("\nResumen de la asignación:")
    print(f"- ID: {activity['id']}")
    print(f"- Actividad: {activity['category']} - {activity['level']}")
    print(f"- Días: {', '.join(activity['weekdays'])}")
    print(f"- Fecha de inicio: {activity['start_date'] or 'Sin asignar'}")
    print(f"- Horario: {activity['start_time']} - {activity['end_time']}")
    print(f"- Plazas: {activity['available_places']}")
    print(
        f"- Ocupación: {activity['occupied_places']}/"
        f"{activity['available_places']} ({activity['occupancy_percentage']}%)"
    )
    print(f"- Espacio: {installation['name']}")
    answer = input("¿Guardar la asignación? (s/n): ").strip().lower()
    if answer not in {"s", "si", "sí"}:
        print("Operación cancelada.")
        return

    assigned = assign_activity_to_installation(
        database, activity["id"], installation["id"]
    )
    print(
        f"Instalación {assigned['installation']} asignada a la actividad "
        f"{activity['id']}."
    )


def _open_registration_period_from_input(database: DataBase) -> None:
    print("\nGESTIÓN GLOBAL DE INSCRIPCIONES")
    print("Elige una acción para socios y otra para no socios.")
    print("1. Programar apertura y cierre")
    print("2. Abrir ahora")
    print("3. Cerrar ahora")
    print("4. No cambiar")
    member_action = _choose_registration_action("socios")
    non_member_action = _choose_registration_action("no socios")

    member_start = member_end = None
    non_member_start = non_member_end = None
    if member_action == "schedule":
        member_start, member_end = _prompt_registration_dates("socios")
    if non_member_action == "schedule":
        non_member_start, non_member_end = _prompt_registration_dates("no socios")

    try:
        result = configurar_inscripciones(
            database,
            member_action,
            non_member_action,
            member_start,
            member_end,
            non_member_start,
            non_member_end,
        )
    except ValueError as error:
        print(f"Datos no válidos: {error}")
        return

    print("\nEstado global de inscripción actualizado:")
    for group, status_key, start_key, end_key in (
        (
            "Socios",
            "member_registration_status",
            "member_registration_start",
            "member_registration_end",
        ),
        (
            "No socios",
            "non_member_registration_status",
            "non_member_registration_start",
            "non_member_registration_end",
        ),
    ):
        status = result[status_key]
        if status == "scheduled":
            print(
                f"- {group}: {status} "
                f"({result[start_key] or 'sin inicio programado'} - "
                f"{result[end_key] or 'sin cierre programado'})"
            )
        else:
            print(f"- {group}: {status}")
    print("El cambio se aplica simultáneamente a todas las actividades.")


def _choose_registration_action(group: str) -> str:
    options = {
        "1": "schedule",
        "2": "open",
        "3": "close",
        "4": "keep",
    }
    while True:
        selection = input(f"Acción para {group} (1/2/3/4): ").strip()
        if selection in options:
            return options[selection]
        print("Selecciona 1, 2, 3 o 4.")


def _prompt_registration_dates(group: str) -> tuple[str, str]:
    while True:
        start_value = input(
            f"Fecha de apertura para {group} (AAAA-MM-DD, hoy o posterior): "
        ).strip()
        start_date = _parse_input_date(start_value, "apertura")
        if start_date is None:
            continue
        if start_date < date.today():
            print("La fecha de apertura no puede ser anterior a hoy.")
            continue

        end_value = input(
            f"Fecha de cierre para {group} (AAAA-MM-DD, posterior a la apertura): "
        ).strip()
        end_date = _parse_input_date(end_value, "cierre")
        if end_date is None:
            continue
        if end_date <= start_date:
            print("La fecha de cierre debe ser posterior a la de apertura.")
            continue
        return start_date.isoformat(), end_date.isoformat()


def _parse_input_date(value: str, field: str) -> date | None:
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        print(f"La fecha de {field} debe tener el formato AAAA-MM-DD.")
        return None
    if parsed_date.isoformat() != value:
        print(f"La fecha de {field} debe tener el formato AAAA-MM-DD.")
        return None
    return parsed_date


def _find_activity_by_reference(
    activities: list[dict[str, object]], selection: str
) -> dict[str, object] | None:
    if not selection:
        return None

    try:
        activity_id = int(selection)
    except ValueError:
        activity_id = None

    normalized_selection = selection.strip().lower()
    for activity in activities:
        activity_name = (
            f"{activity['category']} {activity['level']}"
        ).lower()
        category_name = str(activity["category"]).lower()
        level_name = str(activity["level"]).lower()
        if activity_id is not None and activity["id"] == activity_id:
            return activity
        if normalized_selection in {activity_name, category_name, level_name}:
            return activity
        if normalized_selection in {
            f"{activity['category']} - {activity['level']}",
            f"{activity['category']} {activity['level']}",
        }:
            return activity
    return None


def _choose_option(
    title: str, options: list[ActivityCategory | ActivityLevel]
) -> ActivityCategory | ActivityLevel:
    print(f"\n{title}:")
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option.value}")

    while True:
        selection = input("Selecciona una opción: ").strip()
        try:
            index = int(selection) - 1
            if 0 <= index < len(options):
                return options[index]
        except ValueError:
            pass
        print("Selección no válida.")


def _choose_weekdays() -> list[Weekday]:
    weekdays = list(Weekday)
    selected = []
    while True:
        print("\nDías seleccionados: " + (
            ", ".join(weekday.value for weekday in selected) if selected else "ninguno"
        ))
        print("Selecciona un día para añadirlo o 0 para terminar:")
        for index, weekday in enumerate(weekdays, start=1):
            marker = " (añadido)" if weekday in selected else ""
            print(f"{index}. {weekday.value}{marker}")
        print("0. Terminar selección")

        selection = input("Día: ").strip()
        try:
            index = int(selection)
            if index == 0:
                if selected:
                    return selected
                print("Selecciona al menos un día.")
                continue
            if 1 <= index <= len(weekdays):
                weekday = weekdays[index - 1]
                if weekday in selected:
                    print(f"{weekday.value} ya está seleccionado.")
                else:
                    selected.append(weekday)
                continue
        except ValueError:
            pass
        print("Selecciona un número de día válido.")


def _choose_installation(installations: list[Installation]) -> Installation:
    if not installations:
        raise ValueError("No hay instalaciones compatibles disponibles.")
    print("\nInstalaciones disponibles para esta categoría:")
    for index, installation in enumerate(installations, start=1):
        print(f"{index}. {installation['name']}")

    while True:
        selection = input("Selecciona una instalación: ").strip()
        try:
            index = int(selection) - 1
            if 0 <= index < len(installations):
                return installations[index]
        except ValueError:
            pass
        print("Selección no válida.")


if __name__ == "__main__":
    main()
