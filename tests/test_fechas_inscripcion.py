import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from main import run_menu
from src.activities import add_activity, get_installations
from src.config import SCHEMA
from src.fechas_inscripcion import (
    abrir_plazo_inscripcion,
    get_actividades_no_iniciadas,
    migrate_registration_dates,
)
from src.util.database import DataBase


class RegistrationDateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DataBase(Path(self.temp_dir.name) / "activities.sqlite")
        self.database.executeScript(SCHEMA)
        self.today = date(2026, 5, 1)
        installation_id = get_installations(self.database, "Pilates")[0]["id"]
        self.activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            12,
            installation_id,
            "2026-06-01",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _open_period(self, **overrides):
        values = {
            "member_start": "2026-05-01",
            "member_end": "2026-05-10",
            "non_member_start": "2026-05-11",
            "non_member_end": "2026-05-20",
        }
        values.update(overrides)
        return abrir_plazo_inscripcion(
            self.database,
            self.activity["id"],
            **values,
            today=self.today,
        )

    def test_lists_only_activities_starting_after_today(self):
        installation_id = get_installations(self.database, "Pilates")[0]["id"]
        for start_date in ("2026-05-01", "2026-04-30", None):
            add_activity(
                self.database,
                "Pilates",
                "Medio",
                ["Martes"],
                "12:00",
                "13:00",
                10,
                installation_id,
                start_date,
            )

        activities = get_actividades_no_iniciadas(self.database, self.today)

        self.assertEqual([item["id"] for item in activities], [self.activity["id"]])

    def test_opens_and_persists_both_registration_periods(self):
        period = self._open_period()

        self.assertEqual(period["activity_id"], self.activity["id"])
        stored_activity = self.database.executeQuery(
            """
            SELECT member_registration_start, member_registration_end,
                   non_member_registration_start, non_member_registration_end
            FROM activity WHERE id = ?
            """,
            self.activity["id"],
        )[0]
        self.assertEqual(stored_activity, {
            "member_registration_start": "2026-05-01",
            "member_registration_end": "2026-05-10",
            "non_member_registration_start": "2026-05-11",
            "non_member_registration_end": "2026-05-20",
        })

    def test_rejects_invalid_registration_periods(self):
        invalid_periods = [
            ({"member_start": "2026-04-30"}, "anterior"),
            ({"member_start": "2026-05-10"}, "posterior"),
            ({"non_member_start": "2026-05-10"}, "después"),
            ({"non_member_end": "2026-05-11"}, "posterior"),
            ({"non_member_end": "2026-06-01"}, "antes"),
            ({"member_start": "01-05-2026"}, "formato"),
        ]
        for values, expected_message in invalid_periods:
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, expected_message):
                    self._open_period(**values)

        stored_dates = self.database.executeQuery(
            """
            SELECT member_registration_start, member_registration_end,
                   non_member_registration_start, non_member_registration_end
            FROM activity WHERE id = ?
            """,
            self.activity["id"],
        )[0]
        self.assertTrue(all(value is None for value in stored_dates.values()))

    def test_rejects_missing_or_started_activities(self):
        with self.assertRaisesRegex(ValueError, "No existe"):
            abrir_plazo_inscripcion(
                self.database,
                999,
                "2026-05-01",
                "2026-05-10",
                "2026-05-11",
                "2026-05-20",
                today=self.today,
            )

        self.database.executeUpdateQuery(
            "UPDATE activity SET start_date = ? WHERE id = ?",
            self.today.isoformat(),
            self.activity["id"],
        )
        with self.assertRaisesRegex(ValueError, "ya ha comenzado"):
            self._open_period()

    def test_migration_adds_dates_without_changing_existing_activities(self):
        legacy_database = DataBase(Path(self.temp_dir.name) / "legacy.sqlite")
        legacy_database.executeUpdateQuery(
            """
            CREATE TABLE activity (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                available_places INTEGER NOT NULL
            )
            """
        )
        legacy_database.executeUpdateQuery(
            """
            INSERT INTO activity (
                id, category, level, start_time, end_time, available_places
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            42,
            "Pilates",
            "Medio",
            "10:00",
            "11:00",
            12,
        )

        migrate_registration_dates(legacy_database)

        activity = legacy_database.executeQuery(
            "SELECT id, start_date FROM activity WHERE id = 42"
        )[0]
        self.assertEqual(activity, {"id": 42, "start_date": None})
        columns = legacy_database.executeQuery("PRAGMA table_info(activity)")
        column_names = {column["name"] for column in columns}
        self.assertTrue({
            "start_date",
            "member_registration_start",
            "member_registration_end",
            "non_member_registration_start",
            "non_member_registration_end",
        }.issubset(column_names))

    def test_menu_opens_registration_period_for_selected_activity(self):
        today = date.today()
        activity_start = today + timedelta(days=30)
        inputs = [
            "4",
            str(self.activity["id"]),
            today.isoformat(),
            (today + timedelta(days=5)).isoformat(),
            (today + timedelta(days=6)).isoformat(),
            (today + timedelta(days=10)).isoformat(),
            "0",
        ]
        self.database.executeUpdateQuery(
            "UPDATE activity SET start_date = ? WHERE id = ?",
            activity_start.isoformat(),
            self.activity["id"],
        )

        with patch("builtins.input", side_effect=inputs):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        stored_activity = self.database.executeQuery(
            """
            SELECT member_registration_start, non_member_registration_end
            FROM activity WHERE id = ?
            """,
            self.activity["id"],
        )[0]
        self.assertEqual(stored_activity["member_registration_start"], today.isoformat())
        self.assertEqual(
            stored_activity["non_member_registration_end"],
            (today + timedelta(days=10)).isoformat(),
        )
        self.assertIn(
            "Plazo de inscripción abierto",
            str(print_mock.call_args_list),
        )
