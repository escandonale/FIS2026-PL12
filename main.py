from src.activities import (
    ActivityCategory,
    ActivityLevel,
    RegistrationsAlreadyOpenError,
    Weekday,
    add_activity,
    get_installations,
    list_activities,
    migrate_activity_installation,
    validate_times,
)
from src.config import DATABASE, SCHEMA
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


def main() -> None:
    database = DataBase(DATABASE)
    try:
        database.executeScript(SCHEMA)
        migrate_activity_installation(database)
        run_menu(database)
    except UnexpectedException as error:
        print(f"Error al acceder a la base de datos: {error}")


def run_menu(database: DataBase) -> None:
    while True:
        print("\nCENTRO DEPORTIVO")
        print("1. Añadir actividad")
        print("2. Ver actividades")
        print("0. Salir")
        option = input("Selecciona una opción: ").strip()

        if option == "0":
            print("Hasta luego.")
            return
        if option == "1":
            try:
                activity = create_activity_from_input(database)
                print("\nActividad añadida correctamente:")
                print(f"Categoría: {activity['category']}")
                print(f"Nivel: {activity['level']}")
                print(f"Instalación: {activity['installation']}")
                print(f"Días: {', '.join(activity['weekdays'])}")
                print(
                    f"Horario: {activity['start_time']} - {activity['end_time']}"
                )
                print(f"Plazas disponibles: {activity['available_places']}")
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

        print("Opción no válida. Elige 1, 2 o 0.")


def display_activities(activities: list[dict[str, object]]) -> None:
    print("\nACTIVIDADES DISPONIBLES")
    for activity in activities:
        print(f"\nActividad {activity['id']}")
        print(f"Categoría: {activity['category']}")
        print(f"Nivel: {activity['level']}")
        print(f"Instalación: {activity['installation'] or 'Sin asignar'}")
        print(f"Días: {', '.join(activity['weekdays'])}")
        print(f"Horario: {activity['start_time']} - {activity['end_time']}")
        print(f"Plazas disponibles: {activity['available_places']}")


def create_activity_from_input(database: DataBase) -> dict[str, object]:
    category = _choose_option("Categoría", list(ActivityCategory))
    level = _choose_option("Nivel", list(ActivityLevel))
    weekdays = _choose_weekdays()
    installations = get_installations(database, category)
    installation = _choose_installation(installations)
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
    )


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
