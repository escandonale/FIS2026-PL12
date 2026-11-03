import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src.activities import (
    ActivityCategory,
    ActivityLevel,
    RegistrationsAlreadyOpenError,
    Weekday,
    add_activity,
    assign_activity_to_installation,
    get_installations,
    get_activity,
    list_installation_conflicts,
    list_activities,
    migrate_activity_installation,
    set_activity_occupancy,
)
from main import (
    _choose_weekdays,
    display_existing_conflicts,
    main,
    run_menu,
)
from src.control_plazas import control_plazas, get_activity_seat_report
from src.fechas_inscripcion import abrir_plazo_inscripcion
from src.util.database import DataBase
from src.config import CONSTRAINTS
from src.actividades.actividades_modelo import (
    cancelar_inscripcion,
    get_actividades_disponibles,
    get_inscripciones_cancelables,
    inscribir_no_socio,
    inscribir_socio,
    migrate_cancellation_status,
)
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
        migrate_activity_installation(self.database)
        self.database.executeScript(CONSTRAINTS)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _open_member_registration_period(self, activity_id):
        today = date.today()
        self.database.executeUpdateQuery(
            "UPDATE activity SET start_date = ? WHERE id = ?",
            (today + timedelta(days=30)).isoformat(),
            activity_id,
        )
        abrir_plazo_inscripcion(
            self.database,
            activity_id,
            today.isoformat(),
            (today + timedelta(days=5)).isoformat(),
            (today + timedelta(days=6)).isoformat(),
            (today + timedelta(days=10)).isoformat(),
            today=today,
        )

    def test_add_activity_stores_and_returns_all_details(self):
        activity = add_activity(
            self.database,
            ActivityCategory.SWIMMING,
            ActivityLevel.BEGINNER,
            [Weekday.FRIDAY, Weekday.MONDAY, Weekday.WEDNESDAY],
            "10:00",
            "11:00",
            12,
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
        )

        activities = list_activities(self.database)

        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0], {
            **created,
            "weekdays": ["Lunes", "Miércoles"],
        })

    def test_activity_occupancy_can_be_set_and_percentage_is_returned(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 20
        )

        set_activity_occupancy(self.database, activity["id"], 15)

        listed = list_activities(self.database)[0]
        self.assertEqual(listed["occupied_places"], 15)
        self.assertEqual(listed["occupancy_percentage"], 75.0)

    def test_activity_occupancy_cannot_exceed_capacity(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 20
        )

        with self.assertRaisesRegex(ValueError, "superar la capacidad"):
            set_activity_occupancy(self.database, activity["id"], 21)

    def test_confirmed_enrollment_updates_occupied_places(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 2
        )
        self._open_member_registration_period(activity["id"])
        self.database.executeUpdateQuery(
            """
            INSERT INTO Socios (
                dni, nombre, apellidos, numero_socio, direccion
            ) VALUES (?, ?, ?, ?, ?)
            """,
            "12345678A",
            "Ana",
            "García",
            "S001",
            "Calle Mayor 1",
        )

        receipt = inscribir_socio(
            "12345678A", activity["id"], self.database.dbname
        )

        self.assertEqual(receipt["estado"], "confirmado")
        self.assertEqual(
            get_actividades_disponibles(self.database.dbname)[0]["plazas_libres"],
            1,
        )
        self.assertEqual(
            get_activity(self.database, activity["id"])["occupied_places"], 1
        )

    def test_member_enrollment_requires_a_configured_registration_period(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 2
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO Socios (
                dni, nombre, apellidos, numero_socio, direccion
            ) VALUES (?, ?, ?, ?, ?)
            """,
            "12345678A",
            "Ana",
            "García",
            "S001",
            "Calle Mayor 1",
        )

        with self.assertRaisesRegex(ValueError, "No hay un plazo"):
            inscribir_socio("12345678A", activity["id"], self.database.dbname)

        self.assertEqual(
            self.database.executeQuery(
                "SELECT COUNT(*) AS count FROM inscripcion"
            )[0]["count"],
            0,
        )

    def test_available_activities_are_filtered_by_registration_group(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 2
        )
        self._open_member_registration_period(activity["id"])

        member_activities = get_actividades_disponibles(
            self.database.dbname, es_socio=True
        )
        non_member_activities = get_actividades_disponibles(
            self.database.dbname, es_socio=False
        )

        self.assertEqual([item["id"] for item in member_activities], [activity["id"]])
        self.assertEqual(non_member_activities, [])

    def test_non_member_enrollment_uses_its_own_registration_window(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 2
        )
        today = date(2027, 5, 1)
        self.database.executeUpdateQuery(
            "UPDATE activity SET start_date = ? WHERE id = ?",
            "2027-06-01",
            activity["id"],
        )
        abrir_plazo_inscripcion(
            self.database,
            activity["id"],
            today.isoformat(),
            (today + timedelta(days=5)).isoformat(),
            (today + timedelta(days=6)).isoformat(),
            (today + timedelta(days=10)).isoformat(),
            today=today,
        )

        receipt = inscribir_no_socio(
            "87654321B",
            "Luis",
            "Pérez",
            activity["id"],
            self.database.dbname,
            today=date(2027, 5, 7),
        )

        self.assertEqual(receipt["estado"], "confirmado")
        registration = self.database.executeQuery(
            "SELECT dni, es_socio FROM inscripcion WHERE activity_id = ?",
            activity["id"],
        )[0]
        self.assertEqual(registration, {"dni": "87654321B", "es_socio": 0})

    def test_cancelling_confirmed_registration_promotes_waiting_list(self):
        activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            1,
            start_date="2027-06-01",
        )
        for dni, name, state in (
            ("11111111A", "Ana", "confirmado"),
            ("22222222B", "Luis", "lista de espera"),
        ):
            self.database.executeUpdateQuery(
                """
                INSERT INTO inscripcion (
                    activity_id, nombre, apellidos, dni, estado, es_socio
                ) VALUES (?, ?, ?, ?, ?, 1)
                """,
                activity["id"],
                name,
                "García",
                dni,
                state,
            )
        self.database.executeUpdateQuery(
            "UPDATE activity SET occupied_places = 1 WHERE id = ?",
            activity["id"],
        )

        self.assertTrue(
            cancelar_inscripcion(
                "11111111A",
                activity["id"],
                self.database.dbname,
                today=date(2027, 5, 17),
            )
        )

        statuses = self.database.executeQuery(
            """
            SELECT dni, estado FROM inscripcion
            WHERE activity_id = ? ORDER BY id
            """,
            activity["id"],
        )
        self.assertEqual(statuses, [
            {"dni": "11111111A", "estado": "cancelada"},
            {"dni": "22222222B", "estado": "confirmado"},
        ])
        self.assertEqual(
            get_activity(self.database, activity["id"])["occupied_places"], 1
        )
        self.assertEqual(
            get_inscripciones_cancelables(
                "11111111A", self.database.dbname, today=date(2027, 5, 17)
            ),
            [],
        )

    def test_cancellation_deadline_is_fifteen_days_before_activity_month(self):
        activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            1,
            start_date="2027-06-30",
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado, es_socio
            ) VALUES (?, ?, ?, ?, 'confirmado', 1)
            """,
            activity["id"],
            "Ana",
            "García",
            "11111111A",
        )
        self.database.executeUpdateQuery(
            "UPDATE activity SET occupied_places = 1 WHERE id = ?",
            activity["id"],
        )

        eligible = get_inscripciones_cancelables(
            "11111111A", self.database.dbname, today=date(2027, 5, 17)
        )
        expired = get_inscripciones_cancelables(
            "11111111A", self.database.dbname, today=date(2027, 5, 18)
        )

        self.assertEqual(eligible[0]["fecha_limite_cancelacion"], "2027-05-17")
        self.assertEqual(expired, [])
        with self.assertRaisesRegex(ValueError, "terminó el 2027-05-17"):
            cancelar_inscripcion(
                "11111111A",
                activity["id"],
                self.database.dbname,
                today=date(2027, 5, 18),
            )
        self.assertEqual(
            get_activity(self.database, activity["id"])["occupied_places"], 1
        )

    def test_cancelling_confirmed_registration_without_waitlist_frees_seat(self):
        activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            1,
            start_date="2027-06-01",
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado, es_socio
            ) VALUES (?, ?, ?, ?, 'confirmado', 1)
            """,
            activity["id"],
            "Ana",
            "García",
            "11111111A",
        )
        self.database.executeUpdateQuery(
            "UPDATE activity SET occupied_places = 1 WHERE id = ?",
            activity["id"],
        )

        cancelar_inscripcion(
            "11111111A",
            activity["id"],
            self.database.dbname,
            today=date(2027, 5, 17),
        )

        self.assertEqual(
            get_activity(self.database, activity["id"])["occupied_places"], 0
        )
        self.assertEqual(
            self.database.executeQuery(
                "SELECT estado FROM inscripcion WHERE activity_id = ?",
                activity["id"],
            ),
            [{"estado": "cancelada"}],
        )

    def test_cancellation_migration_preserves_existing_registrations(self):
        legacy_database = DataBase(
            Path(self.temp_dir.name) / "legacy_registrations.sqlite"
        )
        legacy_database.executeScriptFromString(
            """
            CREATE TABLE activity (id INTEGER PRIMARY KEY);
            INSERT INTO activity VALUES (1);
            CREATE TABLE inscripcion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                apellidos TEXT NOT NULL,
                dni TEXT NOT NULL,
                estado TEXT NOT NULL
                    CHECK (estado IN ('confirmado', 'lista de espera')),
                fecha_inscripcion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                es_socio INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (activity_id) REFERENCES activity (id)
            );
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado, es_socio
            ) VALUES (1, 'Ana', 'García', '11111111A', 'confirmado', 1);
            """
        )

        migrate_cancellation_status(legacy_database)
        legacy_database.executeUpdateQuery(
            "UPDATE inscripcion SET estado = 'cancelada' WHERE id = 1"
        )

        self.assertEqual(
            legacy_database.executeQuery(
                "SELECT dni, estado FROM inscripcion WHERE id = 1"
            ),
            [{"dni": "11111111A", "estado": "cancelada"}],
        )
        self.assertEqual(
            legacy_database.executeQuery("PRAGMA foreign_key_check"),
            [],
        )

    def test_full_activity_enrollment_is_added_to_waiting_list(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 1
        )
        self._open_member_registration_period(activity["id"])
        set_activity_occupancy(self.database, activity["id"], 1)
        self.database.executeUpdateQuery(
            """
            INSERT INTO Socios (
                dni, nombre, apellidos, numero_socio, direccion
            ) VALUES (?, ?, ?, ?, ?)
            """,
            "12345678A",
            "Ana",
            "García",
            "S001",
            "Calle Mayor 1",
        )

        receipt = inscribir_socio(
            "12345678A", activity["id"], self.database.dbname
        )

        self.assertEqual(receipt["estado"], "lista de espera")
        self.assertEqual(
            get_activity(self.database, activity["id"])["occupied_places"], 1
        )

    def test_duplicate_enrollment_is_rejected(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 2
        )
        self._open_member_registration_period(activity["id"])
        self.database.executeUpdateQuery(
            """
            INSERT INTO Socios (
                dni, nombre, apellidos, numero_socio, direccion
            ) VALUES (?, ?, ?, ?, ?)
            """,
            "12345678A",
            "Ana",
            "García",
            "S001",
            "Calle Mayor 1",
        )
        inscribir_socio("12345678A", activity["id"], self.database.dbname)

        with self.assertRaisesRegex(ValueError, "ya está inscrito"):
            inscribir_socio("12345678A", activity["id"], self.database.dbname)

    def test_activity_can_be_created_before_installation_is_assigned(self):
        created = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            12,
        )

        self.assertIsNone(created["installation"])
        self.assertIsNone(get_activity(self.database, created["id"])["installation"])

    def test_activity_must_be_assigned_to_compatible_installation(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 12
        )
        swimming_installation_id = get_installations(
            self.database, "Natación"
        )[0]["id"]

        with self.assertRaisesRegex(ValueError, "no está adaptada"):
            assign_activity_to_installation(
                self.database, activity["id"], swimming_installation_id
            )

    def test_activity_can_be_assigned_to_compatible_installation_later(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 12
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]

        assignment = assign_activity_to_installation(
            self.database, activity["id"], gym_id
        )

        self.assertEqual(assignment["installation"], "Gimnasio")
        self.assertEqual(
            get_activity(self.database, activity["id"])["installation"], "Gimnasio"
        )

    def test_overlapping_activity_cannot_be_assigned_to_same_installation(self):
        thursday_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        overlapping_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Jueves"],
            "19:00",
            "21:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]
        assign_activity_to_installation(
            self.database, thursday_activity["id"], gym_id
        )

        with self.assertRaisesRegex(ValueError, "ya está ocupada el Jueves"):
            assign_activity_to_installation(
                self.database, overlapping_activity["id"], gym_id
            )

        self.assertIsNone(
            get_activity(self.database, overlapping_activity["id"])["installation"]
        )

    def test_adjacent_activities_can_use_same_installation(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "19:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Jueves"],
            "19:00",
            "20:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]

        assign_activity_to_installation(self.database, first_activity["id"], gym_id)
        assign_activity_to_installation(self.database, second_activity["id"], gym_id)

        self.assertEqual(list_installation_conflicts(self.database), [])

    def test_conflicts_on_a_different_weekday_do_not_block_assignment(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Viernes"],
            "18:00",
            "20:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]

        assign_activity_to_installation(self.database, first_activity["id"], gym_id)
        assign_activity_to_installation(self.database, second_activity["id"], gym_id)

        self.assertEqual(list_installation_conflicts(self.database), [])

    def test_database_trigger_rejects_overlapping_assignment(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Jueves"],
            "19:00",
            "21:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]
        assign_activity_to_installation(self.database, first_activity["id"], gym_id)

        with self.assertRaises(UnexpectedException):
            self.database.executeUpdateQuery(
                "UPDATE activity SET installation_id = ? WHERE id = ?",
                gym_id,
                second_activity["id"],
            )

    def test_database_trigger_rejects_overlapping_time_change(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Jueves"],
            "20:00",
            "21:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]
        assign_activity_to_installation(self.database, first_activity["id"], gym_id)
        assign_activity_to_installation(self.database, second_activity["id"], gym_id)

        with self.assertRaises(UnexpectedException):
            self.database.executeUpdateQuery(
                "UPDATE activity SET start_time = ? WHERE id = ?",
                "19:00",
                second_activity["id"],
            )

    def test_database_trigger_rejects_overlapping_weekday_addition(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Viernes"],
            "18:00",
            "20:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]
        assign_activity_to_installation(self.database, first_activity["id"], gym_id)
        assign_activity_to_installation(self.database, second_activity["id"], gym_id)

        with self.assertRaises(UnexpectedException):
            self.database.executeUpdateQuery(
                "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
                second_activity["id"],
                "Jueves",
            )

    def test_startup_reports_preexisting_schedule_conflicts(self):
        self.database.executeUpdateQuery(
            "DROP TRIGGER prevent_activity_schedule_conflict_on_day_insert"
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO activity (
                category, level, installation_id,
                start_time, end_time, available_places
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            "Pilates",
            "Medio",
            get_installations(self.database, "Pilates")[0]["id"],
            "18:00",
            "20:00",
            12,
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO activity (
                category, level, installation_id,
                start_time, end_time, available_places
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            "Acondicionamiento Físico",
            "Avanzado",
            get_installations(self.database, "Pilates")[0]["id"],
            "19:00",
            "21:00",
            12,
        )
        self.database.executeUpdateQuery(
            "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
            1,
            "Jueves",
        )
        self.database.executeUpdateQuery(
            "INSERT INTO activity_day (activity_id, weekday) VALUES (?, ?)",
            2,
            "Jueves",
        )

        conflicts = list_installation_conflicts(self.database)
        self.database.executeScript(CONSTRAINTS)
        with patch("builtins.print") as print_mock:
            display_existing_conflicts(self.database)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["weekday"], "Jueves")
        self.assertEqual(conflicts[0]["first_start_time"], "18:00")
        self.assertEqual(conflicts[0]["second_start_time"], "19:00")
        self.assertIn(
            "18:00-20:00 y 19:00-21:00",
            str(print_mock.call_args_list),
        )

    def test_existing_conflict_blocks_new_activity_until_resolved(self):
        first_activity = add_activity(
            self.database, "Pilates", "Medio", ["Jueves"], "18:00", "20:00", 12
        )
        second_activity = add_activity(
            self.database,
            "Acondicionamiento Físico",
            "Avanzado",
            ["Jueves"],
            "19:00",
            "21:00",
            12,
        )
        gym_id = get_installations(self.database, "Pilates")[0]["id"]
        self.database.executeUpdateQuery(
            "UPDATE activity SET installation_id = ? WHERE id = ?",
            gym_id,
            first_activity["id"],
        )
        self.database.executeUpdateQuery(
            "DROP TRIGGER prevent_activity_schedule_conflict_on_assignment"
        )
        self.database.executeUpdateQuery(
            "UPDATE activity SET installation_id = ? WHERE id = ?",
            gym_id,
            second_activity["id"],
        )
        self.database.executeScript(CONSTRAINTS)

        with patch("builtins.input", side_effect=["1", "0"]):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        self.assertEqual(
            self.database.executeQuery("SELECT id FROM activity"),
            [{"id": first_activity["id"]}, {"id": second_activity["id"]}],
        )
        self.assertIn(
            "Las altas están bloqueadas",
            str(print_mock.call_args_list),
        )

    def test_database_rejects_incompatible_category_installation_pair(self):
        swimming_installation_id = get_installations(
            self.database, "Natación"
        )[0]["id"]
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
                swimming_installation_id,
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
            )

    def test_invalid_level_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "(?i)nivel no válida"):
            add_activity(
                self.database,
                "Pilates", "Experto", ["Lunes"], "10:00", "11:00", 10,
            )

    def test_empty_days_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "al menos un día"):
            add_activity(
                self.database,
                "Pilates", "Medio", [], "10:00", "11:00", 10,
            )

    def test_invalid_time_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "posterior"):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "11:00", "10:00", 10,
            )

    def test_invalid_capacity_is_rejected(self):
        for capacity in (0, -1, 1.5, True):
            with self.subTest(capacity=capacity):
                with self.assertRaisesRegex(ValueError, "plazas"):
                    add_activity(
                        self.database,
                        "Pilates", "Medio", ["Lunes"], "10:00", "11:00", capacity,
                    )

    def test_activity_cannot_be_added_after_registrations_open(self):
        self.database.executeUpdateQuery(
            "UPDATE offer SET registrations_open = 1 WHERE id = 1"
        )

        with self.assertRaises(RegistrationsAlreadyOpenError):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 10,
            )

    def test_invalid_input_does_not_create_activity(self):
        with self.assertRaises(ValueError):
            add_activity(
                self.database,
                "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 0,
            )

        self.assertIsNone(get_activity(self.database, 1))

    def test_related_rows_are_rolled_back_if_a_day_insert_fails(self):
        with self.assertRaises(UnexpectedException):
            self.database.executeTransaction(
                """
                INSERT INTO activity (
                    category, level, start_time, end_time, available_places
                )
                SELECT ?, ?, ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM offer
                    WHERE id = 1 AND registrations_open = 0
                )
                """,
                (
                    "Pilates",
                    "Medio", "10:00",
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
            "2026-12-01",
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
        self.assertIsNone(activity["installation"])
        printed_text = "\n".join(
            " ".join(str(argument) for argument in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("Actividad añadida correctamente", printed_text)

    def test_console_menu_assigns_installation_after_activity_creation(self):
        activity = add_activity(
            self.database, "Pilates", "Medio", ["Lunes"], "10:00", "11:00", 12
        )
        user_input = ["3", str(activity["id"]), "1", "0"]

        with patch("builtins.input", side_effect=user_input):
            with patch("builtins.print") as print_mock:
                run_menu(self.database)

        self.assertEqual(
            get_activity(self.database, activity["id"])["installation"], "Gimnasio"
        )
        printed_text = "\n".join(
            " ".join(str(argument) for argument in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("asignada", printed_text)

    def test_console_menu_displays_activity_list(self):
        add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            12,
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
        self.assertIn("Sin asignar", printed_text)

    def test_console_menu_starts_member_enrollment(self):
        with patch("main.iniciar_inscripcion") as enrollment_mock:
            with patch("builtins.input", side_effect=["5", "0"]):
                with patch("builtins.print"):
                    run_menu(self.database)

            enrollment_mock.assert_called_once_with(self.database.dbname)

    def test_console_menu_starts_cancellation_flow(self):
        with patch("main.iniciar_cancelacion") as cancellation_mock:
            with patch("builtins.input", side_effect=["7", "0"]):
                with patch("builtins.print"):
                    run_menu(self.database)

            cancellation_mock.assert_called_once_with(self.database.dbname)

    def test_activity_seat_report_counts_confirmed_and_lists_all_registrations(self):
        activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            2,
            self.pilates_installation_id,
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado,
                fecha_inscripcion, es_socio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            activity["id"],
            "Ana",
            "García",
            "11111111A",
            "confirmado",
            "2026-10-01",
            1,
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado,
                fecha_inscripcion, es_socio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            activity["id"],
            "Luis",
            "Pérez",
            "22222222B",
            "lista de espera",
            "2026-10-02",
            0,
        )

        report = get_activity_seat_report(self.database, activity["id"])

        self.assertEqual(report["installation"], "Gimnasio")
        self.assertEqual(report["aforo_max"], 2)
        self.assertEqual(report["plazas_ocupadas"], 1)
        self.assertEqual(report["plazas_libres"], 1)
        self.assertEqual(
            [
                (registration["nombre"], registration["estado"])
                for registration in report["inscripciones"]
            ],
            [("Ana", "confirmado"), ("Luis", "lista de espera")],
        )

    def test_seat_control_menu_displays_activity_occupancy_and_registration_status(self):
        activity = add_activity(
            self.database,
            "Pilates",
            "Medio",
            ["Lunes"],
            "10:00",
            "11:00",
            2,
            self.pilates_installation_id,
        )
        self.database.executeUpdateQuery(
            """
            INSERT INTO inscripcion (
                activity_id, nombre, apellidos, dni, estado,
                fecha_inscripcion, es_socio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            activity["id"],
            "Ana",
            "García",
            "11111111A",
            "confirmado",
            "2026-10-01",
            1,
        )
        with patch("builtins.input", return_value=str(activity["id"])):
            with patch("builtins.print") as print_mock:
                control_plazas(self.database)

        printed_text = "\n".join(
            " ".join(str(argument) for argument in call.args)
            for call in print_mock.call_args_list
        )
        self.assertIn("Aforo máximo: 2", printed_text)
        self.assertIn("Plazas ocupadas: 1", printed_text)
        self.assertIn("Plazas libres: 1", printed_text)
        self.assertIn("Ana | García | Sí | 2026-10-01 | Inscrito", printed_text)

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
        self.assertIn("Socios", [table["name"] for table in tables])
        self.assertIn("inscripcion", [table["name"] for table in tables])
        self.assertIn("CENTRO DEPORTIVO", str(print_mock.call_args_list))
        triggers = DataBase(database_path).executeQuery(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        )
        self.assertIn(
            "prevent_activity_schedule_conflict_on_assignment",
            [trigger["name"] for trigger in triggers],
        )

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
            "SELECT id, installation_id, occupied_places FROM activity WHERE id = 1"
        )[0]
        self.assertIsNone(activity["installation_id"])
        self.assertEqual(activity["occupied_places"], 0)

    def test_existing_database_with_required_installation_is_migrated(self):
        database_path = Path(self.temp_dir.name) / "assigned_legacy.sqlite"
        legacy_database = DataBase(database_path)
        legacy_database.executeScriptFromString(
            """
            CREATE TABLE installation (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            INSERT INTO installation VALUES (1, 'Gimnasio');

            CREATE TABLE category_installation (
                category TEXT NOT NULL,
                installation_id INTEGER NOT NULL,
                PRIMARY KEY (category, installation_id)
            );
            INSERT INTO category_installation VALUES ('Pilates', 1);

            CREATE TABLE activity (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                installation_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                available_places INTEGER NOT NULL,
                occupied_places INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO activity VALUES (
                1, 'Pilates', 'Medio', 1, '10:00', '11:00', 12, 5
            );

            CREATE TABLE activity_day (
                activity_id INTEGER NOT NULL,
                weekday TEXT NOT NULL,
                PRIMARY KEY (activity_id, weekday),
                FOREIGN KEY (activity_id) REFERENCES activity (id) ON DELETE CASCADE
            );
            INSERT INTO activity_day VALUES (1, 'Lunes');
            """
        )
        schema_path = Path(__file__).parent.parent / "src" / "resources" / "schema.sql"
        legacy_database.executeScript(schema_path)

        migrate_activity_installation(legacy_database)

        activity = get_activity(legacy_database, 1)
        self.assertEqual(activity["installation"], "Gimnasio")
        self.assertEqual(activity["weekdays"], ["Lunes"])
        self.assertEqual(activity["occupied_places"], 5)
        columns = legacy_database.executeQuery("PRAGMA table_info(activity)")
        installation_column = next(
            column for column in columns if column["name"] == "installation_id"
        )
        self.assertEqual(installation_column["notnull"], 0)


if __name__ == "__main__":
    unittest.main()
