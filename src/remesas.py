import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path


_RECEIPTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS recibo (
    nrecibo INTEGER PRIMARY KEY AUTOINCREMENT,
    inscripcion_id INTEGER NOT NULL UNIQUE,
    mes TEXT NOT NULL,
    fecha_emision TEXT NOT NULL,
    importe REAL NOT NULL DEFAULT 0 CHECK (importe >= 0),
    estado TEXT NOT NULL CHECK (estado = 'emitido'),
    FOREIGN KEY (inscripcion_id) REFERENCES inscripcion (id)
);
"""


def _validate_month(month: str) -> tuple[str, str]:
    try:
        parsed_month = datetime.strptime(month, "%Y-%m")
    except ValueError as error:
        raise ValueError("El mes debe tener el formato AAAA-MM.") from error
    if parsed_month.strftime("%Y-%m") != month:
        raise ValueError("El mes debe tener el formato AAAA-MM.")

    month_start = date(parsed_month.year, parsed_month.month, 1)
    if parsed_month.month == 12:
        next_month = date(parsed_month.year + 1, 1, 1)
    else:
        next_month = date(parsed_month.year, parsed_month.month + 1, 1)
    return month_start.isoformat(), next_month.isoformat()


def generar_remesa(
    database_path: str | Path,
    month: str,
    output_directory: str | Path | None = None,
) -> Path:
    month_start, next_month_start = _validate_month(month)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute(_RECEIPTS_SCHEMA)
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")

        registrations = connection.execute(
            """
            SELECT inscripcion.id, inscripcion.fecha_inscripcion
            FROM inscripcion
            JOIN activity ON activity.id = inscripcion.activity_id
            WHERE inscripcion.estado = 'confirmado'
              AND activity.start_date >= ?
              AND activity.start_date < ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM recibo
                  WHERE recibo.inscripcion_id = inscripcion.id
              )
            ORDER BY inscripcion.id
            """,
            (month_start, next_month_start),
        ).fetchall()

        for registration in registrations:
            issuance_date = date.fromisoformat(
                str(registration["fecha_inscripcion"])[:10]
            ).isoformat()
            connection.execute(
                """
                INSERT INTO recibo (
                    inscripcion_id, mes, fecha_emision, importe, estado
                ) VALUES (?, ?, ?, 0, 'emitido')
                """,
                (registration["id"], month, issuance_date),
            )

        receipts = connection.execute(
            """
            SELECT
                recibo.nrecibo,
                recibo.fecha_emision,
                inscripcion.nombre,
                inscripcion.apellidos,
                inscripcion.dni,
                activity.category AS actividad,
                activity.level AS nivel,
                recibo.importe
            FROM recibo
            JOIN inscripcion ON inscripcion.id = recibo.inscripcion_id
            JOIN activity ON activity.id = inscripcion.activity_id
            WHERE recibo.mes = ?
            ORDER BY recibo.nrecibo
            """,
            (month,),
        ).fetchall()
        connection.commit()
    except (sqlite3.Error, ValueError):
        connection.rollback()
        raise
    finally:
        connection.close()

    destination = Path(output_directory) if output_directory else Path.cwd()
    output_path = destination / f"remese_{month}.txt"
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, delimiter=";")
        writer.writerow(
            (
                "NRecibo",
                "Fecha emisión del recibo",
                "Nombre y apellidos",
                "DNI",
                "Actividad",
                "Nivel",
                "Importe",
            )
        )
        for receipt in receipts:
            writer.writerow(
                (
                    receipt["nrecibo"],
                    receipt["fecha_emision"],
                    f"{receipt['nombre']} {receipt['apellidos']}",
                    receipt["dni"],
                    receipt["actividad"],
                    receipt["nivel"],
                    f"{receipt['importe']:.2f}",
                )
            )
    return output_path
