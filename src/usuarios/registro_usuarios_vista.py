from pathlib import Path
from src.config import DATABASE
from .registrar_usuarios import registrar_no_socio

def iniciar_registro_no_socio(db_path: str | Path = DATABASE) -> None:
    print("\n--- REGISTRO DE USUARIO (NO SOCIO) ---")
    
    # Formulario de datos personales[cite: 32]
    nombre = input("Nombre: ").strip()
    apellidos = input("Apellidos: ").strip()
    fecha_nacimiento = input("Fecha de nacimiento (AAAA-MM-DD): ").strip()
    genero = input("Género: ").strip()
    direccion = input("Dirección: ").strip()
    dni = input("DNI: ").strip()
    correo = input("Correo electrónico: ").strip()

    if not all([nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo]):
        print("\n ERROR: Todos los campos son obligatorios.")
        return

    try:
        fecha_alta = registrar_no_socio(
            nombre, apellidos, fecha_nacimiento, genero, 
            direccion, dni, correo, db_path
        )
        
        # Proporcionar justificante por pantalla con datos confirmados[cite: 32]
        print("\n REGISTRO COMPLETADO CON ÉXITO")
        print("--- JUSTIFICANTE DE ALTA ---")
        print(f"Nombre: {nombre} {apellidos}")
        print(f"DNI: {dni}")
        print(f"Fecha de registro: {fecha_alta}")
        print("----------------------------")
        print("Tus datos han sido guardados para agilizar futuras inscripciones.")
        
    except Exception as e:
        print(f"\n ERROR: {e}")