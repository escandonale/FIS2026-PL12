import datetime as dt
import  sqlite3
from datetime import datetime, date



DB_PATH = "centro_deportivo.db"

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn
    

def validar_fecha(start_date, ini_s, fin_s, ini_nos, fin_nos):
    hoy = dt.datetime.now()

    if ini_s < hoy or ini_nos < hoy:
        raise ValueError("La fecha de apertura no puede ser anterior a la fecha actual.")
    
    if fin_s <= ini_s:
        raise ValueError("La fecha de cierre de socios debe ser posterior a su apertura.")
    
    if fin_nos <= ini_nos:
        raise ValueError("La fecha de cierre de no socios debe ser posterior a su apertura.")

    if ini_s >= ini_nos:
        raise ValueError("El periodo de socios debe comenzar antes que el de no socios.")

    if ini_nos < fin_s:
        raise ValueError("Los periodos no pueden solaparse; el de no socios debe empezar tras finalizar el de socios.")

    if fin_s > start_date or fin_nos > start_date:
        raise ValueError("Los plazos de inscripción deben finalizar antes de que comience la actividad.")

    return True

def plazo_inscripcion():
    conn = conectar()
    cursor = conn.cursor()

    hoy = date.today().strftime("%Y-%m-%d")
    
    # lista de actividades 
    query1 = """
        SELECT id, category, level, start_time
        FROM activity
        WHERE datetime(start_time) > datetime(?)
    """
    
    cursor.execute(query1, (hoy,))
    actividades = cursor.fetchall()

    if not actividades:
        print("No hay actividades disponibles.")
        conn.close()
        return

    # Actividades disponibles
    for act in actividades:
        print(f"ID: {act['id']} | Categoría: {act['category']} | Nivel: {act['level']} | Inicio: {act['start_time']}")

    try: 
        id_elegido = int(input("Introduce el ID de la actividad que deseas configurar: ").strip())
    
        actividad_seleccionada = next((a for a in actividades if a['id'] == id_elegido), None)
        if not actividad_seleccionada:
            raise ValueError("El ID introducido no es valido")
    
    

        start_date_str = actividad_seleccionada['start_time']
        start_date_dt = dt.datetime.strptime(start_date_str, "%Y-%m-%d %H:%M")
        
        apertura_socios = dt.datetime.strptime(input("Inicio plazo socios: ").strip(), "%Y-%m-%d")
        cierre_socios = dt.datetime.strptime(input("Cierre plazo socios: ").strip(), "%Y-%m-%d")
        apertura_no_socios = dt.datetime.strptime(input("Inicio plazo no socios: ").strip(), "%Y-%m-%d")
        cierre_no_socios = dt.datetime.strptime(input("Cierre plazo no socios: ").strip(), "%Y-%m-%d")

        
        if validar_fecha(start_date_dt, apertura_socios, cierre_socios, apertura_no_socios, cierre_no_socios):


            query2 = """
                UPDATE activity
                SET ini_socio = ?,
                    fin_socio = ?,
                    ini_no_socio = ?,
                    fin_no_socio = ?
                    WHERE id = ?
                """

            cursor.execute(query2, (
                    apertura_socios.strftime("%Y-%m-%d %H:%M"),
                    cierre_socios.strftime("%Y-%m-%d %H:%M"),
                    apertura_no_socios.strftime("%Y-%m-%d %H:%M"),
                    cierre_no_socios.strftime("%Y-%m-%d %H:%M"),
                    id_elegido
                ))
                
            conn.commit()
    except ValueError as error:
        print("Error al seleccionar una actividad.")