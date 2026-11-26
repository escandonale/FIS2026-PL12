import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import run_menu
from src.activities import get_installations
from src.config import CONSTRAINTS, SCHEMA
from src.ocupacion_instalaciones import get_installation_occupancy_report
from src.util.database import DataBase


class InstallationOccupancyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DataBase(Path(self.temp_dir.name) / "occupancy.sqlite")
        self.database.executeScript(SCHEMA)
        self.database.executeScript(CONSTRAINTS)
        self.installation_id = next(
            installation["id"]
            for installation in get_installations(self.database, "Pilates")
            if installation["name"] == "Gimnasio"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _add_activity(
        self, weekday: str, start_time: str, end_time: str, category: str = "Pilates"
    ) -> None:
        self.database.executeUpdateQuery(
            """
            INSERT INTO activity (
                category, level, installation_id, start_time, end_time,
                available_places
            ) VALUES (?, 'Medio', ?, ?, ?, 10)
            """,
            category,
            self.installation_id,
            start_time,
            end_time,
        )
        activity_id = self.database.executeQuery(
            "SELECT MAX(id) AS id FROM activity"
        )[0]["id"]
        self.database.executeUpdateQuery(
            "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
            activity_id,
            weekday,
        )

    def test_report_counts_partial_hour_slots_and_identifies_peak(self):
        self._add_activity("Lunes", "09:30", "10:30")
        self._add_activity("Martes", "10:00", "11:00", "Acondicionamiento Físico")
        self._add_activity("Miércoles", "11:00", "12:00")

        report = get_installation_occupancy_report(
            self.database,
            self.installation_id,
            "Mañana",
        )

        self.assertEqual(report["hours"], [
            "09:00-10:00",
            "10:00-11:00",
            "11:00-12:00",
        ])
        self.assertIn("Pilates - Medio", report["grid"]["Lunes"]["09:00-10:00"][0])
        self.assertIn("Pilates - Medio", report["grid"]["Lunes"]["10:00-11:00"][0])
        self.assertEqual(report["grid"]["Jueves"]["09:00-10:00"], [])
        self.assertEqual(
            [entry["occupied_days"] for entry in report["hourly_occupancy"]],
            [1, 2, 1],
        )
        self.assertEqual(report["busiest_hours"], ["10:00-11:00"])
        self.assertEqual(report["busiest_days"], ["Lunes"])

    def test_empty_band_has_available_slots_and_no_peak(self):
        report = get_installation_occupancy_report(
            self.database,
            self.installation_id,
            "Tarde",
        )

        self.assertEqual(report["hours"], [
            "18:00-19:00",
            "19:00-20:00",
            "20:00-21:00",
            "21:00-22:00",
        ])
        self.assertTrue(
            all(
                not report["grid"][weekday][hour]
                for weekday in report["weekdays"]
                for hour in report["hours"]
            )
        )
        self.assertEqual(report["busiest_hours"], [])
        self.assertEqual(report["busiest_days"], [])

    def test_console_menu_opens_the_occupancy_report(self):
        inputs = ["11", "9999", str(self.installation_id), "x", "1", "0"]
        with patch("builtins.input", side_effect=inputs):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        printed_text = "\n".join(
            str(argument)
            for call in print_mock.call_args_list
            for argument in call.args
        )
        self.assertIn("OCUPACIÓN SEMANAL", printed_text)
        self.assertIn("Disponible", printed_text)
        self.assertIn("No existe un espacio con ese ID", printed_text)
        self.assertIn("Selecciona una opción de franja válida", printed_text)

    def test_report_rejects_unknown_installation_and_time_band(self):
        with self.assertRaisesRegex(ValueError, "franja horaria"):
            get_installation_occupancy_report(
                self.database,
                self.installation_id,
                "Noche",
            )
        with self.assertRaisesRegex(ValueError, "No existe el espacio"):
            get_installation_occupancy_report(
                self.database,
                9999,
                "Mañana",
            )


if __name__ == "__main__":
    unittest.main()
