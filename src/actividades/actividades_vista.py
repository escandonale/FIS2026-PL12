from actividades.actividades_modelo import get_actividades_disponibles, inscribir_socio

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