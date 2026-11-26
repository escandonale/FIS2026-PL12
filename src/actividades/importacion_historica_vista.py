from src.actividades.importacion_historica_modelo import (
    importar_inscripciones_csv,
)
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


def iniciar_importacion_csv(database: DataBase) -> None:
    print("\n--- IMPORTAR INSCRIPCIONES HISTÓRICAS (CSV) ---")
    print(
        "Columnas: activity_id,nombre,apellidos,dni,estado,fecha_inscripcion,es_socio"
    )
    ruta = input("Introduce la ruta del archivo CSV: ").strip()
    if not ruta:
        print("Operación cancelada: no se indicó ninguna ruta.")
        return

    try:
        resultado = importar_inscripciones_csv(database, ruta)
    except (FileNotFoundError, ValueError) as error:
        print(f"\nERROR: {error}")
        return
    except UnexpectedException as error:
        print(f"\nError al acceder a la base de datos: {error}")
        return

    if resultado["valido_100"]:
        print(
            f"\nIMPORTACIÓN EXITOSA: archivo válido al 100% "
            f"({len(resultado['ok'])} inscripciones guardadas)."
        )
        return

    print("\nIMPORTACIÓN PARCIAL COMPLETADA (SE DETECTARON INCONSISTENCIAS)")
    print(f"Total OKs importados: {len(resultado['ok'])}")
    print(f"Total KOs descartados: {len(resultado['ko'])}")

    print("\n--- DETALLE DE ERRORES (KOs) ---")
    for ko in resultado["ko"]:
        print(f"  Fila {ko['fila']}: {' | '.join(ko['errores'])}")

    print("\n--- DETALLE DE IMPORTADOS (OKs) ---")
    if resultado["ok"]:
        for ok in resultado["ok"]:
            print(
                f"  Fila {ok['fila']}: DNI {ok['dni']} -> "
                f"Actividad {ok['activity_id']} ({ok['estado']})"
            )
    else:
        print("  Ninguna inscripción válida para importar.")

    if resultado["ruta_reporte"]:
        print(f"\nReporte guardado en: {resultado['ruta_reporte']}")