import tempfile
import unittest
from pathlib import Path

from activitites import list_installation_conflicts
from src.config import CONSTRAINTS, DATA, SCHEMA
from src.util.database import DataBase


class SampleDataTests(unittest.TestCase):
    def test_seed_creates_complete_sample_offer_and_prioritized_registrations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DataBase(Path(temp_dir) / "sample.sqlite")
            database.executeScript(SCHEMA)
            database.executeScript(CONSTRAINTS)
            database.executeScript(DATA)

            activities = database.executeQuery(
                """
                SELECT
                    activity.id,
                    activity.start_date,
                    activity.start_time,
                    activity.end_time,
                    activity.available_places,
                    activity.occupied_places,
                    activity.member_registration_start,
                    activity.member_registration_end,
                    activity.non_member_registration_start,
                    activity.non_member_registration_end,
                    installation.name AS installation,
                    COUNT(
                        CASE WHEN inscripcion.estado = 'confirmado' THEN 1 END
                    ) AS confirmed_count
                FROM activity
                JOIN installation ON installation.id = activity.installation_id
                LEFT JOIN inscripcion ON inscripcion.activity_id = activity.id
                GROUP BY activity.id
                ORDER BY activity.id
                """
            )
            self.assertEqual(len(activities), 10)
            for activity in activities:
                self.assertTrue(activity["start_date"])
                self.assertTrue(activity["start_time"])
                self.assertTrue(activity["end_time"])
                self.assertTrue(activity["installation"])
                self.assertTrue(activity["member_registration_start"])
                self.assertTrue(activity["member_registration_end"])
                self.assertTrue(activity["non_member_registration_start"])
                self.assertTrue(activity["non_member_registration_end"])
                self.assertEqual(
                    activity["occupied_places"], activity["confirmed_count"]
                )
                occupancy_percentage = (
                    activity["occupied_places"]
                    / activity["available_places"]
                    * 100
                )
                if activity["id"] == 1:
                    self.assertEqual(occupancy_percentage, 100)
                else:
                    self.assertGreaterEqual(occupancy_percentage, 50)
                    self.assertLessEqual(occupancy_percentage, 90)

            counts = database.executeQuery(
                """
                SELECT
                    SUM(CASE WHEN es_socio = 1 THEN 1 ELSE 0 END) AS members,
                    SUM(CASE WHEN es_socio = 0 THEN 1 ELSE 0 END) AS non_members
                FROM inscripcion
                """
            )[0]
            self.assertEqual(counts["non_members"], counts["members"] * 2)
            profile_counts = database.executeQuery(
                """
                SELECT
                    (SELECT COUNT(*) FROM Socios) AS members,
                    (SELECT COUNT(*) FROM no_socio) AS non_members
                """
            )[0]
            self.assertEqual(
                profile_counts["non_members"], profile_counts["members"] * 2
            )

            member_last = database.executeQuery(
                "SELECT MAX(id) AS id FROM inscripcion WHERE es_socio = 1"
            )[0]["id"]
            non_member_first = database.executeQuery(
                "SELECT MIN(id) AS id FROM inscripcion WHERE es_socio = 0"
            )[0]["id"]
            self.assertLess(member_last, non_member_first)
            self.assertEqual(
                database.executeQuery("PRAGMA foreign_key_check"),
                [],
            )
            self.assertEqual(list_installation_conflicts(database), [])


if __name__ == "__main__":
    unittest.main()
