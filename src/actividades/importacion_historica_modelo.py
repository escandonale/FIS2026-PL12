import csv
from datetime import date
from pathlib import Path

from src.util.database import DataBase


CABECERAS_OBLIGATORIAS = (
    "activity_id",
    "nombre",
    "apellidos",
    "dni",
    "estado",
    "fecha_inscripcion",
    "es_socio",
)
ESTADOS_VALIDOS = {"confirmado", "lista de espera", "cancelada"}


def importar_inscripciones_csv(
    database: DataBase,
    ruta_csv: str | Path,
    ruta_reporte: str | Path | None = None,
) -> dict[str, object]:
    """Valida un CSV de inscripciones históricas, importa los OKs y guarda reporte de KOs."""
    path = Path(ruta_csv)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo CSV: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames:
            raise ValueError("El archivo CSV está vacío.")

        cabeceras = [c.strip() for c in lector.fieldnames if c is not None]
        faltantes = [c for c in CABECERAS_OBLIGATORIAS if c not in cabeceras]
        if faltantes:
            raise ValueError(
                f"Faltan columnas obligatorias en el CSV: {', '.join(faltantes)}."
            )

        actividades_existentes = {
            row["id"]
            for row in database.executeQuery("SELECT id FROM activity")
        }
        inscripciones_en_bd = {
            (row["dni"].strip().upper(), row["activity_id"])
            for row in database.executeQuery(
                "SELECT dni, activity_id FROM inscripcion"
            )
        }

        registros_ok: list[dict[str, object]] = []
        registros_ko: list[dict[str, object]] = []
        vistos_en_csv: set[tuple[str, int]] = set()

        for num_fila, fila in enumerate(lector, start=2):
            errores_fila = _validar_fila(
                fila,
                actividades_existentes,
                inscripciones_en_bd,
                vistos_en_csv,
            )
            if errores_fila:
                registros_ko.append(
                    {
                        "fila": num_fila,
                        "errores": errores_fila,
                    }
                )
                continue

            activity_id = int(fila["activity_id"].strip())
            dni = fila["dni"].strip().upper()
            vistos_en_csv.add((dni, activity_id))
            registros_ok.append(
                {
                    "fila": num_fila,
                    "activity_id": activity_id,
                    "nombre": fila["nombre"].strip(),
                    "apellidos": fila["apellidos"].strip(),
                    "dni": dni,
                    "estado": fila["estado"].strip().lower(),
                    "fecha_inscripcion": fila["fecha_inscripcion"].strip(),
                    "es_socio": int(fila["es_socio"].strip()),
                }
            )

    if registros_ok:
        queries = [
            (
                """
                INSERT INTO inscripcion (
                    activity_id, nombre, apellidos, dni,
                    estado, fecha_inscripcion, es_socio
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reg["activity_id"],
                    reg["nombre"],
                    reg["apellidos"],
                    reg["dni"],
                    reg["estado"],
                    reg["fecha_inscripcion"],
                    reg["es_socio"],
                ),
            )
            for reg in registros_ok
        ]
        database.executeTransactionQueries(
            queries,
            expected_row_counts=tuple(1 for _ in registros_ok),
        )

    archivo_reporte: Path | None = None
    if registros_ko:
        archivo_reporte = (
            Path(ruta_reporte)
            if ruta_reporte is not None
            else path.with_name(f"{path.stem}_reporte_errores.txt")
        )
        _guardar_reporte(archivo_reporte, registros_ok, registros_ko)

    return {
        "valido_100": len(registros_ko) == 0,
        "total_filas": len(registros_ok) + len(registros_ko),
        "ok": registros_ok,
        "ko": registros_ko,
        "ruta_reporte": str(archivo_reporte) if archivo_reporte else None,
    }


def _validar_fila(
    fila: dict[str, str | None],
    actividades_existentes: set[int],
    inscripciones_en_bd: set[tuple[str, int]],
    vistos_en_csv: set[tuple[str, int]],
) -> list[str]:
    errores: list[str] = []

    raw_activity = (fila.get("activity_id") or "").strip()
    nombre = (fila.get("nombre") or "").strip()
    apellidos = (fila.get("apellidos") or "").strip()
    dni = (fila.get("dni") or "").strip().upper()
    estado = (fila.get("estado") or "").strip().lower()
    fecha_str = (fila.get("fecha_inscripcion") or "").strip()
    raw_socio = (fila.get("es_socio") or "").strip()

    if not nombre:
        errores.append("Falta el dato obligatorio 'nombre'.")
    if not apellidos:
        errores.append("Falta el dato obligatorio 'apellidos'.")
    if not dni:
        errores.append("Falta el dato obligatorio 'dni'.")

    activity_id: int | None = None
    if not raw_activity:
        errores.append("Falta el dato obligatorio 'activity_id'.")
    else:
        try:
            activity_id = int(raw_activity)
            if activity_id not in actividades_existentes:
                errores.append(
                    f"La actividad con ID {activity_id} no existe en la base de datos."
                )
        except ValueError:
            errores.append(
                f"Formato incorrecto en 'activity_id': '{raw_activity}' debe ser numérico."
            )

    if not estado:
        errores.append("Falta el dato obligatorio 'estado'.")
    elif estado not in ESTADOS_VALIDOS:
        errores.append(
            f"Estado '{estado}' no válido (permitidos: confirmado, lista de espera, cancelada)."
        )

    if not fecha_str:
        errores.append("Falta el dato obligatorio 'fecha_inscripcion'.")
    else:
        try:
            fecha_valida = date.fromisoformat(fecha_str)
            if fecha_valida.isoformat() != fecha_str:
                raise ValueError
        except ValueError:
            errores.append(
                f"Formato de fecha inválido '{fecha_str}' (debe ser AAAA-MM-DD)."
            )

    if raw_socio not in {"0", "1"}:
        errores.append(
            f"Formato incorrecto en 'es_socio': '{raw_socio}' (debe ser 0 o 1)."
        )

    if dni and activity_id is not None:
        clave = (dni, activity_id)
        if clave in vistos_en_csv:
            errores.append(
                f"Registro duplicado en el CSV (DNI {dni} en actividad {activity_id})."
            )
        elif clave in inscripciones_en_bd:
            errores.append(
                f"Registro duplicado: el DNI {dni} ya está inscrito en la actividad {activity_id}."
            )

    return errores


def _guardar_reporte(
    ruta_reporte: Path,
    registros_ok: list[dict[str, object]],
    registros_ko: list[dict[str, object]],
) -> None:
    lineas = [
        "REPORTE DE IMPORTACIÓN DE INSCRIPCIONES HISTÓRICAS",
        f"Total OKs importados: {len(registros_ok)}",
        f"Total KOs descartados: {len(registros_ko)}",
        "",
        "--- ERRORES (KOs) ---",
    ]
    for item in registros_ko:
        detalle = " | ".join(item["errores"])
        lineas.append(f"Fila {item['fila']}: {detalle}")

    lineas.append("")
    lineas.append("--- IMPORTADOS (OKs) ---")
    if registros_ok:
        for item in registros_ok:
            lineas.append(
                f"Fila {item['fila']}: DNI {item['dni']} -> Actividad {item['activity_id']} ({item['estado']})"
            )
    else:
        lineas.append("Ninguno.")

    ruta_reporte.write_text("\n".join(lineas) + "\n", encoding="utf-8")