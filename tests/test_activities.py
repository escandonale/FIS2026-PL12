import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.activities import (
    ActivityCategory,
    ActivityLevel,
    RegistrationsAlreadyOpenError,
    Weekday,
    add_activity,
    get_installations,
    get_activity,
    list_activities,
    migrate_activity_installation,
)
from main import _choose_weekdays, main, run_menu
from src.util.database import DataBase
from src.util.unexpectedException import UnexpectedException


class ActivityFunctionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "activities.sqlite"
        self.database = DataBase(database_path)
        schema_path = Path(__file__).parent.parent / "src" / "resources" / "schema.sql"
        self.database.executeScript(schema_path)
        self.pilates_installation_id = get_installations(
            self.database, "Pilates"
        )[0]["id"]
        self.swimming_installation_id = get_installations(
            self.database, "Natación"
        )[0]["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_activity_stores_and_returns_all_details(self):
        activity = add_activity(
            self.database,
            ActivityCategory.SWIMMING,
            ActivityLevel.BEGINNER,
            [Weekday.FRIDAY, Weekday.MONDAY, Weekday.WEDNESDAY],
            "10:00",
            "11:00",
            12,
            self.swimming_installation_id,
        )

        self.assertEqual(
            activity["weekdays"],
            ["Lunes", "Miércoles", "Viernes"],
        )
        self.assertEqual(get_activity(self.database, activity["id"]), activity)

    def test_same_category_level_and_periodicity_can_be_added_twice(self):
        details = (
            "Pilates",
            "Medio",
            ["Lunes", "Miércoles"],
            "10:00",
            "11:00",
            10,
            self.pilates_installation_id,
        )

        first = add_activity(self.database, *details)
        second = add_activity(self.database, *details)

        self.assertNotEqual(first["id"], second["id"])

    def test_list_activities_returns_details_and_weekdays(self):
        created = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Miércoles", "Lunes"],
            "10:00",
            "11:00",
            12,
            self.pilates_installation_id,
        )

        activities = list_activities(self.database)

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0], {
            **created,
            "weekdays": ["Lunes", "Miércoles"],
        })

    def test_activity_must_use_an_installation_compatible_with_its_category(self):
        with self.assertRaisesRegex(ValueError, "no está adaptada"):
            add_activity(
                self.database,
                "Pilates",
                "Medio",
                ["Lunes"],
                "10:00",
                "11:00",
                12,
                self.swimming_installation_id,
            )

    def test_database_rejects_incompatible_category_installation_pair(self):
        with self.assertRaises(UnexpectedException):
            self.database.executeUpdateQuery(
                """
                INSERT INTO activity (
                    category, level, installation_id,
                    start_time, end_time, available_places
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                "Pilates",
                "Medio",
                self.swimming_installation_id,
                "10:00",
                "11:00",
                12,
            )

        self.assertEqual(
            self.database.executeQuery("SELECT id FROM activity"),
            [],
        )

    def test_installations_are_filtered_by_category(self):
        pools = [row["name"] for row in get_installations(self.database, "Natación")]
        courts = [row["name"] for row in get_installations(self.database, "Tenis")]

        self.assertEqual(pools, ["Piscina Pequeña", "Piscina Grande"])
        self.assertEqual(courts, ["Pista de Ténis 1", "Pista de Ténis 2"])

    def test_list_activities_returns_empty_list_when_there_are_no_activities(self):
        self.assertEqual(list_activities(self.database), [])

    def test_invalid_category_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "(?i)categoría no válida"):
            add_activity(
                self.database,
                "Boxeo", "Medio", ["Lunes"], "10:00", "11:00", 10,
                self.pilates_installation_id,
            )

    def test_invalid_level_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "(?i)nivel no válida"):
            add_activity(
                self.database,
                "Pilates", "Experto", ["Lunes"], "10:00", "11:00", 10,
                self.pilates_installation_id,
            )

    def test_empty_days_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "al menos un día"):
            add_activity(
                self.database,
                "Pilates", "Medio", [], "10:00", "11:00", 10,
                self.pilates_installation_id,
            )

    def test_invalid_time_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "posterior"):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "11:00", "10:00", 10,
                self.pilates_installation_id,
            )

    def test_invalid_capacity_is_rejected(self):
        for capacity in (0, -1, 1.5, True):
            with self.subTest(capacity=capacity):
                with self.assertRaisesRegex(ValueError, "plazas"):
                    add_activity(
                        self.database,
                        "Pilates", "Medio", ["Lunes"], "10:00", "11:00", capacity,
                        self.pilates_installation_id,
                    )

    def test_activity_cannot_be_added_after_registrations_open(self):
        self.database.executeUpdateQuery(
            "UPDATE offer SET registrations_open = 1 WHERE id = 1"
        )

        with self.assertRaises(RegistrationsAlreadyOpenError):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 10,
                self.pilates_installation_id,
            )

    def test_invalid_input_does_not_create_activity(self):
        with self.assertRaises(ValueError):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 0,
                self.pilates_installation_id,
            )

        self.assertIsNone(get_activity(self.database, 1))

    def test_related_rows_are_rolled_back_if_a_day_insert_fails(self):
        with self.assertRaises(UnexpectedException):
            self.database.executeTransaction(
                """
                INSERT INTO activity (
                    category, level, installation_id,
                    start_time, end_time, available_places
                )
                SELECT ?, ?, ?, ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM offer
                    WHERE id = 1 AND registrations_open = 0
                )
                """,
                (
                    "Pilates",
                    "Medio",
                    self.pilates_installation_id,
                    "10:00",
                    "11:00",
                    10,
                ),
                "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
                [("Día inválido",)],
            )

        self.assertIsNone(get_activity(self.database, 1))

    def test_console_menu_creates_activity_and_displays_confirmation(self):
        user_input = [
            "1",  # menu
            "2",  # category
            "1",  # level
            "1",  # Monday
            "3",  # Wednesday
            "5",  # Friday
            "0",  # finish selecting days
            "1",  # installation
            "10:00",
            "11:00",
            "12",
            "0",  # exit
        ]
        with patch("builtins.input", side_effect=user_input):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        activity = get_activity(self.database, 1)
        self.assertEqual(activity["category"], "Pilates")
        self.assertEqual(activity["weekdays"], ["Lunes", "Miércoles", "Viernes"])
        self.assertEqual(activity["installation"], "Gimnasio")
        printed_text = "\n".join(
            " ".join(str(argument) for argument in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("Actividad añadida correctamente", printed_text)

    def test_console_menu_displays_activity_list(self):
        add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            12,
            self.pilates_installation_id,
        )
        user_input = ["2", "0"]

        with patch("builtins.input", side_effect=user_input):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        printed_text = "\n".join(
            " ".join(str(argument) for argument in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("ACTIVIDADES DISPONIBLES", printed_text)
        self.assertIn("Pilates", printed_text)
        self.assertIn("Lunes", printed_text)
        self.assertIn("Gimnasio", printed_text)

    def test_weekday_selector_adds_days_one_by_one_until_zero(self):
        with patch("builtins.input", side_effect=["1", "1", "3", "0"]):
            with patch("builtins.print"):
                selected = _choose_weekdays()

        self.assertEqual(selected, [Weekday.MONDAY, Weekday.WEDNESDAY])

    def test_application_entry_point_initializes_database_and_shows_menu(self):
        database_path = Path(self.temp_dir.name) / "application.sqlite"
        with patch("main.DATABASE", database_path):
            with patch("builtins.input", return_value="0"):
                with patch("builtins.print") as print_mock:
                    main()

        tables = DataBase(database_path).executeQuery(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        self.assertIn("activity", [table["name"] for table in tables])
        self.assertIn("installation", [table["name"] for table in tables])
        self.assertIn("CENTRO DEPORTIVO", str(print_mock.call_args_list))

    def test_existing_database_is_migrated_without_dropping_activities(self):
        database_path = Path(self.temp_dir.name) / "legacy.sqlite"
        legacy_database = DataBase(database_path)
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
                category, level, start_time, end_time, available_places
            ) VALUES (?, ?, ?, ?, ?)
            """,
            "Pilates",
            "Medio",
            "10:00",
            "11:00",
            12,
        )
        schema_path = Path(__file__).parent.parent / "src" / "resources" / "schema.sql"
        legacy_database.executeScript(schema_path)
        migrate_activity_installation(legacy_database)

        activity = legacy_database.executeQuery(
            "SELECT id, installation_id FROM activity WHERE id = 1"
        )[0]
        self.assertIsNone(activity["installation_id"])


if __name__ == "__main__":
    unittest.main()
