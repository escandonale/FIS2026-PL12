import sqlite3
import datetime

DB_PATH = "sample.db" 

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def get_actividades_disponibles():
    conn = conectar()
    cursor = conn.cursor()
    
    query = """
        SELECT a.id, a.nombre, a.modalidad, a.nivel, a.periodicidad, a.plazas_totales,
               (a.plazas_totales - (
                   SELECT COUNT(*) FROM Inscripciones i 
                   WHERE i.id_actividad = a.id AND i.estado = 'confirmada'
               )) AS plazas_libres
        FROM Actividades a
    """
    cursor.execute(query)
    actividades = cursor.fetchall()
    conn.close()
    return actividades

def inscribir_socio(dni, id_actividad):
    conn = conectar()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, nombre, apellidos, numero_socio FROM Socios WHERE dni = ?", (dni,))
        socio = cursor.fetchone()
        if not socio:
            raise ValueError("No se ha encontrado ningún socio con ese DNI.")
            
        cursor.execute("""
            SELECT nombre, nivel, periodicidad, plazas_totales,
                (SELECT COUNT(*) FROM Inscripciones WHERE id_actividad = ? AND estado = 'confirmada') as plazas_ocupadas
            FROM Actividades WHERE id = ?
        """, (id_actividad, id_actividad))
        actividad = cursor.fetchone()
        
        if not actividad:
            raise ValueError("La actividad seleccionada no existe.")
            
        estado_inscripcion = 'lista_espera'
        if actividad['plazas_ocupadas'] < actividad['plazas_totales']:
            estado_inscripcion = 'confirmada'
            
        cursor.execute("""
            INSERT INTO Inscripciones (id_socio, id_actividad, estado)
            VALUES (?, ?, ?)
        """, (socio['id'], id_actividad, estado_inscripcion))
        
        conn.commit()
        
        return {
            "nombre": f"{socio['nombre']} {socio['apellidos']}",
            "numero_socio": socio['numero_socio'],
            "actividad": actividad['nombre'],
            "nivel": actividad['nivel'],
            "periodicidad": actividad['periodicidad'],
            "estado": estado_inscripcion
        }
        
    except sqlite3.IntegrityError:
        raise ValueError("El socio ya está inscrito en esta actividad.")
    finally:
        conn.close()