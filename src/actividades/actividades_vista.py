from actividades.actividades_modelo import get_actividades_disponibles, inscribir_socio
from actividades.actividades_modelo import get_inscripciones_cancelables, cancelar_inscripcion

def iniciar_inscripcion():
    print("\n--- NUEVA INSCRIPCIÓN DE SOCIO ---")
    dni = input("Introduce el DNI del socio: ")
    
    print("\nActividades disponibles:")
    actividades = get_actividades_disponibles()
    for act in actividades:
        print(f"[{act['id']}] {act['nombre']} ({act['modalidad']} - {act['nivel']}) | {act['periodicidad']} | Plazas libres: {act['plazas_libres']}")
        
    id_act = input("\nIntroduce el ID de la actividad a inscribirse: ")
    
    try:
        justificante = inscribir_socio(dni, int(id_act))
        print("\n--- JUSTIFICANTE DE INSCRIPCIÓN ---")
        print(f"Socio: {justificante['nombre']} (Nº {justificante['numero_socio']})")
        print(f"Actividad: {justificante['actividad']} ({justificante['nivel']})")
        print(f"Horario: {justificante['periodicidad']}")
        print(f"ESTADO: {justificante['estado'].upper()}")
        print("-----------------------------------")
    except Exception as e:
        print(f"\nERROR: {e}")


def iniciar_cancelacion():
    print("\n--- CANCELAR INSCRIPCIÓN ---")
    dni = input("Introduce tu DNI: ")
    
    actividades = get_inscripciones_cancelables(dni)
    
    if not actividades:
        print("No tienes inscripciones activas o el plazo de cancelación ha expirado.")
        return
        
    print("\nTus actividades disponibles para cancelar:")
    for act in actividades:
        print(f"ID: {act['id']} | Nombre: {act['nombre']} | Estado actual: {act['estado']}")
        
    id_act = input("\nIntroduce el ID de la actividad que deseas cancelar (o 'salir'): ")
    if id_act.lower() == 'salir':
        return
        
    try:
        if cancelar_inscripcion(dni, int(id_act)):
            print("\n Tu inscripción ha sido cancelada correctamente.")
            print("Tu plaza ha quedado libre y el pago asociado ha sido anulado.")
    except Exception as e:
        print(f"\n ERROR: {e}")