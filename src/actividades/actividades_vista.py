import sqlite3
from pathlib import Path

from src.config import DATABASE
from .actividades_modelo import get_actividades_disponibles, inscribir_socio


def iniciar_inscripcion(db_path: str | Path = DATABASE) -> None:
    print("\n--- NUEVA INSCRIPCIÓN DE SOCIO ---")
    dni = input("Introduce el DNI del socio: ").strip()

    try:
        actividades = get_actividades_disponibles(db_path)
        if not actividades:
            print("No hay actividades disponibles para inscripción.")
            return

        print("\nActividades disponibles:")
        for act in actividades:
            print(
                f"[{act['id']}] {act['nombre']} "
                f"({act['modalidad']} - {act['nivel']}) | "
                f"{act['periodicidad']} | Plazas libres: {act['plazas_libres']}"
            )

        id_act = input("\nIntroduce el ID de la actividad a inscribirse: ").strip()
        try:
            activity_id = int(id_act)
        except ValueError:
            print("El identificador de actividad debe ser numérico.")
            return

        justificante = inscribir_socio(dni, activity_id, db_path)
        print("\n--- JUSTIFICANTE DE INSCRIPCIÓN ---")
        print(
            f"Socio: {justificante['nombre']} (ID {justificante['socio_id']})"
        )
        print(f"Actividad: {justificante['actividad']} ({justificante['nivel']})")
        print(f"Horario: {justificante['periodicidad']}")
        print(f"ESTADO: {justificante['estado'].upper()}")
        print("-----------------------------------")
    except ValueError as error:
        print(f"\nERROR: {error}")
    except sqlite3.Error as error:
        print(f"\nError al acceder a la base de datos: {error}")