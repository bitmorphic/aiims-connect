import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositorySmokeTests(unittest.TestCase):
    def test_environment_template_uses_local_mysql(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("DB_HOST=127.0.0.1", content)
        self.assertIn("DB_NAME=aiims_connect", content)

    def test_legacy_schema_names_are_used(self):
        routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("Patient_UHID", routes)
        self.assertIn("Doctor_ID", routes)
        self.assertIn("Dest_Branch_ID", routes)
        self.assertIn("admin_staff", routes)

    def test_public_landing_page_is_the_root_view(self):
        routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
        landing = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        self.assertIn('@bp.route("/")', routes)
        self.assertIn("One patient.", landing)
        self.assertIn("Every branch.", landing)

    def test_legacy_bootstrap_generator_is_present(self):
        self.assertTrue((ROOT / "scripts" / "prepare_railway_schema.py").exists())
        self.assertFalse((ROOT / "sql" / "schema.sql").exists())


if __name__ == "__main__":
    unittest.main()
