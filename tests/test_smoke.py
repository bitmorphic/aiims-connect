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
        self.assertIn("doctor_branch[\"Branch_ID\"] != branch_id()", routes)

    def test_public_landing_page_is_the_root_view(self):
        routes = self.read("app", "routes.py")
        landing = self.read("templates", "landing.html")
        self.assertIn('@bp.route(\"/\")', routes)
        self.assertIn("One patient.", landing)
        self.assertIn("Every branch.", landing)

    def test_database_verifier_is_read_only(self):
        verifier = self.read("scripts", "init_db.py")
        self.assertIn("information_schema.TABLES", verifier)
        self.assertNotIn("CREATE TABLE", verifier.upper())
        self.assertNotIn("DROP TABLE", verifier.upper())

    def test_railway_bootstrap_generator_and_demo_previewer_exist(self):
        self.assertTrue((ROOT / "scripts" / "prepare_railway_schema.py").exists())
        seeder = self.read("scripts", "seed_demo.py")
        self.assertIn("--apply", seeder)
        self.assertIn("PREVIEW ONLY", seeder)


if __name__ == "__main__":
    unittest.main()