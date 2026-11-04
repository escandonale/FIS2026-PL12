import sqlite3
from pathlib import Path
from src.config import DATABASE

def conectar(db_path: str | Path = DATABASE) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
#solo se ha implementado registrar un no socioo
def registrar_no_socio(
    nombre: str, apellidos: str, fecha_nacimiento: str, genero: str, 
    direccion: str, dni: str, correo: str, db_path: str | Path = DATABASE
) -> str:
    conn = conectar(db_path)
    try:
        # Validar si ya existe el DNI en el sistema
        existente = conn.execute(
            "SELECT 1 FROM no_socio WHERE dni = ?", (dni,)
        ).fetchone()
        
        if existente:
            raise ValueError("Ya existe un usuario registrado con este DNI.")

        # Guardar la información en el sistema
        conn.execute(
            """
            INSERT INTO no_socio (
                nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nombre, apellidos, fecha_nacimiento, genero, direccion, dni, correo)
        )
        conn.commit()

        # Obtener la fecha de alta generada automáticamente por la BD[cite: 32]
        usuario = conn.execute(
            "SELECT fecha_registro FROM no_socio WHERE dni = ?", (dni,)
        ).fetchone()
        
        return usuario["fecha_registro"]
    finally:
        conn.close()