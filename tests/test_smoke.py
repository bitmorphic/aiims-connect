import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositorySmokeTests(unittest.TestCase):
    def read(self, *parts):
        return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")

    def test_environment_template_uses_local_mysql(self):
        content = self.read(".env.example")
        self.assertIn("DB_HOST=127.0.0.1", content)
        self.assertIn("DB_NAME=aiims_connect", content)

    def test_routes_target_the_exported_schema(self):
        routes = self.read("app", "routes.py")
        for token in ("Patient_UHID", "Doctor_ID", "Dest_Branch_ID",
                      "admin_staff", "RegisterPatient", "BookAppointment",
                      "AdmitPatient", "DischargePatient", "AcceptReferral"):
            with self.subTest(token=token):
                self.assertIn(token, routes)

    def test_branch_staff_cannot_book_another_branch_doctor(self):
        routes = self.read("app", "routes.py")
        self.assertIn("doctor_record[\"Branch_ID\"] != branch_id()", routes)

    def test_public_landing_page_is_the_root_view(self):
        routes = self.read("app", "routes.py")
        landing = self.read("templates", "landing.html")
        self.assertIn('@bp.route(\"/\")', routes)
        self.assertIn("One patient.", landing)
        self.assertIn("One patient · Every branch", landing)

    def test_database_verifier_is_read_only(self):
        verifier = self.read("scripts", "init_db.py")
        self.assertIn("information_schema.TABLES", verifier)
        self.assertNotIn("CREATE TABLE", verifier.upper())
        self.assertNotIn("DROP TABLE", verifier.upper())


    def test_portable_schema_contains_expected_objects(self):
        schema = self.read("sql", "schema.sql")
        self.assertEqual(schema.count("CREATE TABLE "), 24)
        self.assertEqual(schema.count("CREATE TRIGGER "), 14)
        self.assertEqual(schema.count("CREATE PROCEDURE "), 11)
        self.assertEqual(schema.count("CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW "), 7)
        self.assertNotRegex(schema, r"(?im)^\s*(DROP|USE)\b")

    def test_railway_bootstrap_and_fhir_first_cleanup_tools_exist(self):
        self.assertTrue((ROOT / "scripts" / "prepare_railway_schema.py").exists())
        self.assertTrue((ROOT / "scripts" / "clean_demo_data.py").exists())
        seeder = self.read("scripts", "seed_demo.py")
        self.assertIn("Demo data seeding is disabled", seeder)
        self.assertNotIn("RegisterPatient", seeder)

    def test_doctor_roster_migration_and_workspace_exist(self):
        migration = self.read("sql", "migrations", "2026_11_demo_doctor_roster.sql")
        self.assertIn("Demo Dr. Aditi Sharma", migration)
        self.assertIn("Demo Dr. Meera Rathore", migration)
        self.assertIn("WHERE NOT EXISTS", migration)
        self.assertTrue((ROOT / "templates" / "doctors.html").exists())
        routes = self.read("app", "routes.py")
        self.assertIn('@bp.route("/doctors", methods=["GET", "POST"])', routes)
        self.assertIn('@bp.get("/appointments/availability")', routes)

    def test_workspace_ui_includes_fhir_first_architecture_and_accessible_mobile_nav(self):
        base = self.read("templates", "base.html")
        dashboard = self.read("templates", "dashboard.html")
        landing = self.read("templates", "landing.html")
        self.assertIn('data-mobile-nav', base)
        self.assertIn("FHIR clinical records", base)
        self.assertIn("FHIR clinical records", dashboard)
        self.assertIn("FHIR R4 clinical histories", landing)
        self.assertIn("Not real AIIMS records", landing)


if __name__ == "__main__":
    unittest.main()