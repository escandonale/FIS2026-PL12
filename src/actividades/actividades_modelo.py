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


def get_inscripciones_cancelables(dni):
    conn = conectar()
    cursor = conn.cursor()
    
    # Obtiene solo las actividades a las que está inscrito y en plazo de cancelación
    query = """
        SELECT a.id, a.nombre, i.estado, a.fecha_limite_cancelacion
        FROM Actividades a
        JOIN Inscripciones i ON a.id = i.id_actividad
        JOIN Socios s ON i.id_socio = s.id
        WHERE s.dni = ? AND i.estado IN ('confirmada', 'lista_espera')
        AND a.fecha_limite_cancelacion >= CURRENT_DATE
    """
    cursor.execute(query, (dni,))
    actividades = cursor.fetchall()
    conn.close()
    return actividades

def cancelar_inscripcion(dni, id_actividad):
    conn = conectar()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM Socios WHERE dni = ?", (dni,))
        socio = cursor.fetchone()
        if not socio:
            raise ValueError("Socio no encontrado.")
            
        id_socio = socio['id']
        
        # Cancela la inscripción liberando la plaza y anula el pago asociado[cite: 24]
        cursor.execute("""
            UPDATE Inscripciones 
            SET estado = 'cancelada', estado_pago = 'anulado'
            WHERE id_socio = ? AND id_actividad = ? AND estado != 'cancelada'
        """, (id_socio, id_actividad))
        
        if cursor.rowcount == 0:
            raise ValueError("No se pudo cancelar. Verifica que estés inscrito y en plazo.")
            
        conn.commit()
        return True
    finally:
        conn.close()