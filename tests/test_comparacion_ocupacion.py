import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from main import run_menu
from src.activities import add_activity, get_installations
from src.asistencia import iniciar_registro_asistencia, save_attendance_session
from src.comparacion_ocupacion import (
    _select_week_start,
    attendance_chart_lines,
    get_activity_attendance_history,
    get_weekly_occupancy_comparison,
)
from src.config import CONSTRAINTS, SCHEMA
from src.util.database import DataBase


class OccupancyComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DataBase(Path(self.temp_dir.name) / "comparison.sqlite")
        self.database.executeScript(SCHEMA)
        self.database.executeScript(CONSTRAINTS)
        self.installation_id = next(
            installation["id"]
            for installation in get_installations(self.database, "Pilates")
            if installation["name"] == "Gimnasio"
        )
        self.week_start = date(2026, 11, 23)
        self.activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes", "Miércoles"],
            "10:00",
            "11:00",
            10,
            self.installation_id,
        )
        self.registration_ids = [
            self._add_registration("11111111A"),
            self._add_registration("22222222B"),
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def _add_registration(self, dni: str) -> int:
        registration_id = self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado, es_socio
            ) VALUES (?, ?, ?, ?, 'confirmado', 1)
            """,
            self.activity["id"],
            "Socio",
            "Prueba",
            dni,
        )
        assert registration_id is not None
        return registration_id

    def _save_monday_attendance(self, attendance: dict[int, bool]) -> None:
        save_attendance_session(
            self.database,
            self.activity["id"],
            self.week_start,
            attendance,
            today=self.week_start,
        )

    def test_comparison_uses_saved_snapshot_and_marks_unrecorded_sessions(self):
        self._save_monday_attendance(
            {self.registration_ids[0]: True, self.registration_ids[1]: False}
        )
        self._add_registration("33333333C")

        report = get_weekly_occupancy_comparison(
            self.database,
            self.installation_id,
            self.week_start,
        )

        monday, wednesday = report
        self.assertEqual(monday["planned_count"], 2)
        self.assertEqual(monday["actual_count"], 1)
        self.assertEqual(monday["attendance_percentage"], 50.0)
        self.assertEqual(monday["difference"], -1)
        self.assertEqual(wednesday["planned_count"], 3)
        self.assertIsNone(wednesday["actual_count"])
        self.assertIsNone(wednesday["attendance_percentage"])
        self.assertEqual(self.database.executeQuery("PRAGMA foreign_key_check"), [])

    def test_reregistering_a_session_replaces_its_records_and_updates_graph(self):
        self._save_monday_attendance(
            {self.registration_ids[0]: True, self.registration_ids[1]: False}
        )
        self.database.executeUpdateQuery(
            "UPDATE inscripcion SET estado = 'cancelada' WHERE id = ?",
            self.registration_ids[0],
        )
        self._save_monday_attendance(
            {self.registration_ids[0]: True, self.registration_ids[1]: True}
        )

        history = get_activity_attendance_history(
            self.database,
            self.activity["id"],
            self.week_start,
        )

        self.assertEqual(
            history,
            [{
                "session_date": self.week_start.isoformat(),
                "planned_count": 2,
                "actual_count": 2,
            }],
        )
        graph = attendance_chart_lines(history)
        self.assertIn("P [", graph[1])
        self.assertIn("R [", graph[1])

    def test_zero_planned_attendance_is_recorded_but_has_no_efficiency_ratio(self):
        self.database.executeUpdateQuery(
            "UPDATE inscripcion SET estado = 'cancelada' WHERE activity_id = ?",
            self.activity["id"],
        )
        self._save_monday_attendance({})

        monday = get_weekly_occupancy_comparison(
            self.database,
            self.installation_id,
            self.week_start,
        )[0]

        self.assertEqual(monday["planned_count"], 0)
        self.assertEqual(monday["actual_count"], 0)
        self.assertIsNone(monday["attendance_percentage"])
        self.assertEqual(monday["difference"], 0)

    def test_comparison_is_limited_to_the_selected_installation(self):
        other_installation_id = next(
            installation["id"]
            for installation in get_installations(self.database, "Pilates")
            if installation["name"] == "Sala de Actividades 1"
        )
        add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            10,
            other_installation_id,
        )

        report = get_weekly_occupancy_comparison(
            self.database,
            self.installation_id,
            self.week_start,
        )

        self.assertEqual(
            {entry["activity_id"] for entry in report},
            {self.activity["id"]},
        )

    def test_attendance_menu_saves_a_session(self):
        with patch(
            "builtins.input",
            side_effect=[str(self.activity["id"]), "1", "p", "a"],
        ):
            with patch("builtins.print"):
                iniciar_registro_asistencia(self.database)

        session = self.database.executeQuery(
            "SELECT planned_count FROM attendance_session WHERE activity_id = ?",
            self.activity["id"],
        )
        self.assertEqual(len(session), 1)
        self.assertEqual(session[0]["planned_count"], 2)
        self.assertEqual(
            self.database.executeQuery(
                """
                SELECT SUM(attended) AS present_count
                FROM attendance_record WHERE activity_id = ?
                """,
                self.activity["id"],
            )[0]["present_count"],
            1,
        )

    def test_saving_attendance_rejects_future_and_unscheduled_dates(self):
        attendance = {
            self.registration_ids[0]: True,
            self.registration_ids[1]: False,
        }
        with self.assertRaisesRegex(ValueError, "fecha futura"):
            save_attendance_session(
                self.database,
                self.activity["id"],
                self.week_start,
                attendance,
                today=date(2026, 11, 22),
            )
        with self.assertRaisesRegex(ValueError, "no está programada"):
            save_attendance_session(
                self.database,
                self.activity["id"],
                date(2026, 11, 24),
                attendance,
                today=date(2026, 11, 24),
            )

    def test_menu_opens_the_weekly_occupancy_comparison(self):
        with patch(
            "builtins.input",
            side_effect=["12", str(self.installation_id), "", "0", "0"],
        ):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        printed_text = "\n".join(
            str(argument)
            for call in print_mock.call_args_list
            for argument in call.args
        )
        self.assertIn("PLANIFICADA Y REAL", printed_text)
        self.assertIn("ACTIVIDADES DE LA SEMANA", printed_text)

    def test_week_navigation_defaults_to_current_week_and_can_go_back(self):
        with patch("builtins.input", side_effect=["a", ""]):
            week_start = _select_week_start(date(2026, 11, 26))

        self.assertEqual(week_start, date(2026, 11, 16))


if __name__ == "__main__":
    unittest.main()
