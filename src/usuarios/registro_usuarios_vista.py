from pathlib import Path

from src.config import DATABASE
from src.util.pretty_tables import print_table

from .registrar_usuarios import registrar_no_socio, registrar_socio


def iniciar_registro_socio(db_path: str | Path = DATABASE) -> None:
    print("\n--- REGISTRO DE SOCIO ---")
    genero = _solicitar_genero()
    nombre = input("Nombre: ").strip()
    apellidos = input("Apellidos: ").strip()
    dni = input("DNI: ").strip()
    numero_socio = input("Número de socio: ").strip()
    direccion = input("Dirección: ").strip()

    if not all([nombre, apellidos, dni, numero_socio, direccion]):
        print("\nERROR: Todos los campos son obligatorios.")
        return

    try:
        dni_registrado = registrar_socio(
            nombre,
            apellidos,
            genero,
            dni,
            numero_socio,
            direccion,
            db_path,
        )
        print("REGISTRO DE SOCIO COMPLETADO CON ÉXITO")
        print_table(
            "JUSTIFICANTE DE ALTA",
            ["Nombre", "Género", "DNI", "Número de socio"],
            [[f"{nombre} {apellidos}", genero, dni_registrado, numero_socio]],
        )
        print("Ya puedes inscribirte con prioridad en las actividades.")
    except ValueError as error:
        print(f"\nERROR: {error}")


def iniciar_registro_no_socio(db_path: str | Path = DATABASE) -> None:
    print("\n--- REGISTRO DE USUARIO (NO SOCIO) ---")

    genero = _solicitar_genero()
    nombre = input("Nombre: ").strip()
    apellidos = input("Apellidos: ").strip()
    fecha_nacimiento = input("Fecha de nacimiento (AAAA-MM-DD): ").strip()
    direccion = input("Dirección: ").strip()
    dni = input("DNI: ").strip()
    correo = input("Correo electrónico: ").strip()

    if not all([nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo]):
        print("\nERROR: Todos los campos son obligatorios.")
        return

    try:
        fecha_alta = registrar_no_socio(
            nombre,
            apellidos,
            fecha_nacimiento,
            genero,
            direccion,
            dni,
            correo,
            db_path,
        )

        print("REGISTRO COMPLETADO CON ÉXITO")
        print_table(
            "JUSTIFICANTE DE ALTA",
            ["Nombre", "Género", "DNI", "Fecha de registro"],
            [[f"{nombre} {apellidos}", genero, dni, fecha_alta]],
        )
        print("Tus datos han sido guardados para agilizar futuras inscripciones.")
    except ValueError as error:
        print(f"\nERROR: {error}")


def _solicitar_genero() -> str:
    print("Género: m = masculino, f = femenino, n = no decirlo")
    while True:
        genero = input("Introduce m, f o n: ").strip().lower()
        if genero in {"m", "f", "n"}:
            return genero
        print("El género debe ser m, f o n.")