from pathlib import Path

from src.config import DATABASE

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
        print("\nREGISTRO DE SOCIO COMPLETADO CON ÉXITO")
        print("--- JUSTIFICANTE DE ALTA ---")
        print(f"Nombre: {nombre} {apellidos}")
        print(f"Género: {genero}")
        print(f"DNI: {dni_registrado}")
        print(f"Número de socio: {numero_socio}")
        print("----------------------------")
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

        print("\nREGISTRO COMPLETADO CON ÉXITO")
        print("--- JUSTIFICANTE DE ALTA ---")
        print(f"Nombre: {nombre} {apellidos}")
        print(f"Género: {genero}")
        print(f"DNI: {dni}")
        print(f"Fecha de registro: {fecha_alta}")
        print("----------------------------")
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