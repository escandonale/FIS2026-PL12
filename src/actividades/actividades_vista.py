import sqlite3
from pathlib import Path

from src.config import DATABASE
from src.util.pretty_tables import print_table
from .actividades_modelo import (
    cancelar_inscripcion,
    get_actividades_disponibles,
    get_inscripciones_cancelables,
    inscribir_no_socio,
    inscribir_socio,
)


def iniciar_inscripcion(db_path: str | Path = DATABASE) -> None:
    print("\n--- NUEVA INSCRIPCIÓN ---")
    group = input("¿Inscripción de socio? (s/n): ").strip().lower()
    if group not in {"s", "n"}:
        print("Indica 's' para socio o 'n' para no socio.")
        return

    try:
        activities = get_actividades_disponibles(db_path, es_socio=group == "s")
        if not activities:
            group_name = "socios" if group == "s" else "no socios"
            print(f"No hay actividades con plazo abierto para {group_name}.")
            return

        dni = input("Introduce el DNI: ").strip()
        if group == "s":
            name = ""
            surname = ""
        else:
            name = input("Introduce el nombre: ").strip()
            surname = input("Introduce los apellidos: ").strip()

        print_table(
            "ACTIVIDADES DISPONIBLES",
            ["ID", "Actividad", "Nivel", "Horario", "Plazas libres"],
            [
                [
                    activity["id"],
                    activity["nombre"],
                    activity["nivel"],
                    activity["periodicidad"],
                    activity["plazas_libres"],
                ]
                for activity in activities
            ],
        )

        selection = input("\nIntroduce el ID de la actividad: ").strip()
        try:
            activity_id = int(selection)
        except ValueError:
            print("El identificador de actividad debe ser numérico.")
            return

        if group == "s":
            receipt = inscribir_socio(dni, activity_id, db_path)
        else:
            receipt = inscribir_no_socio(
                dni, name, surname, activity_id, db_path
            )
        print_table(
            "JUSTIFICANTE DE INSCRIPCIÓN",
            ["Persona", "Actividad", "Nivel", "Horario", "Estado"],
            [[
                receipt["nombre"],
                receipt["actividad"],
                receipt["nivel"],
                receipt["periodicidad"],
                receipt["estado"].upper(),
            ]],
        )
    except ValueError as error:
        print(f"\nERROR: {error}")
    except sqlite3.Error as error:
        print(f"\nError al acceder a la base de datos: {error}")


def iniciar_cancelacion(db_path: str | Path = DATABASE) -> None:
    print("\n--- CANCELAR INSCRIPCIÓN ---")
    dni = input("Introduce tu DNI: ").strip()
    try:
        activities = get_inscripciones_cancelables(dni, db_path)
        if not activities:
            print(
                "No tienes inscripciones activas dentro del plazo de cancelación."
            )
            return

        print_table(
            "INSCRIPCIONES QUE PUEDES CANCELAR",
            ["ID", "Actividad", "Estado", "Fecha límite"],
            [
                [
                    activity["id"],
                    activity["nombre"],
                    activity["estado"],
                    activity["fecha_limite_cancelacion"],
                ]
                for activity in activities
            ],
        )

        selection = input(
            "\nIntroduce el ID de la actividad a cancelar (o 'salir'): "
        ).strip()
        if selection.lower() == "salir":
            return
        try:
            activity_id = int(selection)
        except ValueError:
            print("El identificador de actividad debe ser numérico.")
            return

        cancelar_inscripcion(dni, activity_id, db_path)
        print("La inscripción se ha cancelado correctamente.")
        print("Si había una plaza confirmada, se ha ofrecido a la lista de espera.")
    except ValueError as error:
        print(f"\nERROR: {error}")
    except sqlite3.Error as error:
        print(f"\nError al acceder a la base de datos: {error}")
