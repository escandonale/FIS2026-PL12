from src.activities import (
    ActivityCategory,
    ActivityLevel,
    RegistrationsAlreadyOpenError,
    Weekday,
    add_activity,
    assign_activity_to_installation,
    get_activity,
    get_installations,
    list_installation_conflicts,
    list_activities,
    migrate_activity_installation,
    validate_times,
)
from src.control_plazas import control_plazas
from src.config import DATABASE, SCHEMA
from src.fechas_inscripcion import (
    abrir_plazo_inscripcion,
    get_actividades_no_iniciadas,
    migrate_registration_dates,
)
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


def main() -> None:
    database = DataBase(DATABASE)
    try:
        database.executeScript(SCHEMA)
        migrate_activity_installation(database)
        migrate_registration_dates(database)
        run_menu(database)
    except UnexpectedException as error:
        print(f"Error al acceder a la base de datos: {error}")


def run_menu(database: DataBase) -> None:
    while True:
        conflicts = list_installation_conflicts(database)
        print("\nCENTRO DEPORTIVO")
        if conflicts:
            display_existing_conflicts(database, conflicts)
            print("Las altas están bloqueadas hasta resolver los solapamientos.")
        else:
            print("1. Añadir actividad")
        print("2. Ver actividades")
        print("3. Abrir plazo de inscripción")
        print("4. Controlar plazas e inscripciones")
        
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
                        _open_registration_period_from_input(database)
                    except UnexpectedException as error:
                        print(f"Error al acceder a la base de datos: {error}")
                    continue
        if option == "4":
            try:
                control_plazas(database)
            except UnexpectedException as error:
                print(f"Error al acceder a la base de datos: {error}")
            continue

        

        print("Opción no válida. Elige 1, 2, 3, 4 o 0.")


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


def create_activity_from_input(database: DataBase) -> dict[str, object]:
    category = _choose_option("Categoría", list(ActivityCategory))
    level = _choose_option("Nivel", list(ActivityLevel))
    weekdays = _choose_weekdays()
    installations = get_installations(database, category)
    installation = _choose_installation(installations)
    start_date = input("Fecha de inicio de la actividad (AAAA-MM-DD): ").strip()
    start_time = input("Hora de inicio (HH:MM): ").strip()

    while True:
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

    return add_activity(
        database,
        category,
        level,
        weekdays,
        start_time,
        end_time,
        available_places,
        installation["id"],
        start_date,
    )


def _open_registration_period_from_input(database: DataBase) -> None:
    activities = get_actividades_no_iniciadas(database)
    if not activities:
        print("No hay actividades futuras con fecha de inicio asignada.")
        return

    print("\nACTIVIDADES NO INICIADAS")
    for activity in activities:
        print(
            f"[{activity['id']}] {activity['category']} - {activity['level']} "
            f"| Inicio: {activity['start_date']}"
        )

    selection = input("\nIntroduce el ID de la actividad: ").strip()
    try:
        activity_id = int(selection)
    except ValueError:
        print("Introduce un ID válido.")
        return
    if not any(activity["id"] == activity_id for activity in activities):
        print("El ID no corresponde a una actividad no iniciada.")
        return

    while True:
        member_start = input(
            "Inicio de inscripción para socios (AAAA-MM-DD): "
        ).strip()
        member_end = input(
            "Fin de inscripción para socios (AAAA-MM-DD): "
        ).strip()
        non_member_start = input(
            "Inicio de inscripción para no socios (AAAA-MM-DD): "
        ).strip()
        non_member_end = input(
            "Fin de inscripción para no socios (AAAA-MM-DD): "
        ).strip()
        try:
            period = abrir_plazo_inscripcion(
                database,
                activity_id,
                member_start,
                member_end,
                non_member_start,
                non_member_end,
            )
        except ValueError as error:
            print(f"Datos no válidos: {error}")
            continue
        print(
            f"Plazo de inscripción abierto para la actividad {period['activity_id']}."
        )
        return


def _choose_option(title: str, options: list[ActivityCategory | ActivityLevel]):
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


def _choose_installation(installations: list[dict[str, object]]) -> dict[str, object]:
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
