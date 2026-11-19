from datetime import date
from pathlib import Path

from src.util.database import DataBase


ESTADOS_VALIDOS = {"cobrado", "devuelto"}
CABECERA_ESPERADA = ("id_recibo", "estado", "fecha_operacion", "motivo")


def importar_respuesta_banco(
    database: DataBase, ruta_fichero: str | Path
) -> dict[str, object]:
    """Valida e importa un fichero de respuesta bancaria.

    Formato de cada línea: id_recibo;estado;fecha_operacion;motivo
    Si se detecta cualquier inconsistencia, no se actualiza ningún recibo.
    """
    path = Path(ruta_fichero)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el fichero: {path}")

    lineas = path.read_text(encoding="utf-8").splitlines()
    if not any(linea.strip() for linea in lineas):
        raise ValueError("El fichero está vacío.")

    errores: list[str] = []
    registros_validos: list[dict[str, object]] = []
    ids_vistos: set[int] = set()

    for num_linea, linea_bruta in enumerate(lineas, start=1):
        linea = linea_bruta.strip()
        if not linea:
            continue

        partes = [parte.strip() for parte in linea.split(";")]

        if num_linea == 1 and tuple(p.lower() for p in partes) == CABECERA_ESPERADA:
            continue

        if len(partes) != 4:
            errores.append(
                f"Línea {num_linea}: formato incorrecto "
                "(se esperan 4 campos separados por ';': "
                "id_recibo;estado;fecha_operacion;motivo)."
            )
            continue

        id_str, estado_raw, fecha_str, motivo = partes
        estado = estado_raw.lower()

        try:
            recibo_id = int(id_str)
            if recibo_id <= 0:
                raise ValueError
        except ValueError:
            errores.append(
                f"Línea {num_linea}: el identificador de recibo '{id_str}' no es válido."
            )
            continue

        if recibo_id in ids_vistos:
            errores.append(
                f"Línea {num_linea}: el recibo {recibo_id} aparece duplicado en el fichero."
            )
            continue
        ids_vistos.add(recibo_id)

        if estado not in ESTADOS_VALIDOS:
            errores.append(
                f"Línea {num_linea}: estado '{estado_raw}' no válido "
                "(debe ser 'cobrado' o 'devuelto')."
            )
            continue

        try:
            fecha_valida = date.fromisoformat(fecha_str)
            if fecha_valida.isoformat() != fecha_str:
                raise ValueError
        except ValueError:
            errores.append(
                f"Línea {num_linea}: fecha '{fecha_str}' no válida (formato AAAA-MM-DD)."
            )
            continue

        recibo = database.executeQuery(
            "SELECT id, importe, estado FROM recibo WHERE id = ?",
            recibo_id,
        )
        if not recibo:
            errores.append(
                f"Línea {num_linea}: no existe ningún recibo con ID {recibo_id}."
            )
            continue

        registros_validos.append(
            {
                "id": recibo_id,
                "estado": estado,
                "fecha_respuesta": fecha_str,
                "motivo_devolucion": motivo if estado == "devuelto" and motivo else None,
                "importe": float(recibo[0]["importe"]),
            }
        )

    if errores:
        return {
            "exito": False,
            "errores": errores,
            "total_procesados": 0,
            "cobrados": 0,
            "devueltos": 0,
            "importe_cobrado": 0.0,
            "importe_devuelto": 0.0,
        }

    if not registros_validos:
        raise ValueError("El fichero no contiene registros de recibos para importar.")

    queries = [
        (
            """
            UPDATE recibo
            SET estado = ?,
                fecha_respuesta = ?,
                motivo_devolucion = ?
            WHERE id = ?
            """,
            (
                reg["estado"],
                reg["fecha_respuesta"],
                reg["motivo_devolucion"],
                reg["id"],
            ),
        )
        for reg in registros_validos
    ]
    database.executeTransactionQueries(
        queries,
        expected_row_counts=tuple(1 for _ in registros_validos),
    )

    cobrados = [r for r in registros_validos if r["estado"] == "cobrado"]
    devueltos = [r for r in registros_validos if r["estado"] == "devuelto"]

    return {
        "exito": True,
        "errores": [],
        "total_procesados": len(registros_validos),
        "cobrados": len(cobrados),
        "devueltos": len(devueltos),
        "importe_cobrado": round(sum(r["importe"] for r in cobrados), 2),
        "importe_devuelto": round(sum(r["importe"] for r in devueltos), 2),
    }