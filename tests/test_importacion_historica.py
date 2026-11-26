import tempfile
import unittest
from pathlib import Path

from src.activities import add_activity
from src.actividades.importacion_historica_modelo import (
    importar_inscripciones_csv,
)
from src.config import SCHEMA
from src.util.database import DataBase


class ImportacionHistoricaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DataBase(Path(self.temp_dir.name) / "historicos.sqlite")
        self.database.executeScript(SCHEMA)
        self.activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 10
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_importa_csv_valido_al_100_por_ciento(self):
        csv_path = Path(self.temp_dir.name) / "inscripciones_ok.csv"
        csv_path.write_text(
            "activity_id,nombre,apellidos,dni,estado,fecha_inscripcion,es_socio\n"
            f"{self.activity['id']},Ana,García,12345678A,confirmado,2025-10-01,1\n"
            f"{self.activity['id']},Luis,Pérez,87654321B,lista de espera,2025-10-02,0\n",
            encoding="utf-8",
        )

        resultado = importar_inscripciones_csv(self.database, csv_path)

        self.assertTrue(resultado["valido_100"])
        self.assertEqual(len(resultado["ok"]), 2)
        self.assertEqual(len(resultado["ko"]), 0)
        self.assertIsNone(resultado["ruta_reporte"])

        filas = self.database.executeQuery("SELECT dni FROM inscripcion ORDER BY id")
        self.assertEqual(
            [f["dni"] for f in filas],
            ["12345678A", "87654321B"],
        )

    def test_importa_oks_descarta_kos_y_guarda_reporte(self):
        csv_path = Path(self.temp_dir.name) / "inscripciones_mixto.csv"
        csv_path.write_text(
            "activity_id,nombre,apellidos,dni,estado,fecha_inscripcion,es_socio\n"
            f"{self.activity['id']},Ana,García,12345678A,confirmado,2025-10-01,1\n"
            f"{self.activity['id']},Ana,García,12345678A,confirmado,2025-10-01,1\n"
            f"{self.activity['id']},Pedro,López,,confirmado,2025-10-03,0\n"
            f"{self.activity['id']},Marta,Ruiz,11111111C,confirmado,fecha-mal,1\n",
            encoding="utf-8",
        )

        resultado = importar_inscripciones_csv(self.database, csv_path)

        self.assertFalse(resultado["valido_100"])
        self.assertEqual(len(resultado["ok"]), 1)
        self.assertEqual(len(resultado["ko"]), 3)
        self.assertEqual([ko["fila"] for ko in resultado["ko"]], [3, 4, 5])

        reporte_path = Path(resultado["ruta_reporte"])
        self.assertTrue(reporte_path.is_file())
        contenido_reporte = reporte_path.read_text(encoding="utf-8")
        self.assertIn("Fila 3:", contenido_reporte)
        self.assertIn("Fila 4:", contenido_reporte)
        self.assertIn("Fila 5:", contenido_reporte)

        filas = self.database.executeQuery("SELECT dni FROM inscripcion")
        self.assertEqual(filas, [{"dni": "12345678A"}])


if __name__ == "__main__":
    unittest.main()