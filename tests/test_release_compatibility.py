import unittest
from unittest.mock import patch

from app import create_app


def missing_table_error():
    error = RuntimeError("Table 'aiims_connect.fhir_resource' doesn't exist")
    error.errno = 1146
    return error


class ReleaseCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def sign_in(self, role="doctor"):
        with self.client.session_transaction() as state:
            state["login_id"] = 7
            state["role"] = role
            state["staff_id"] = 12
            state["branch_id"] = 1
            state["patient_uhid"] = "AIC0000001"

    def test_fhir_read_returns_service_unavailable_before_migration(self):
        self.sign_in()
        with patch("app.fhir.fetch_one", side_effect=missing_table_error()):
            response = self.client.get("/fhir/Patient/synthea-123")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["resourceType"], "OperationOutcome")
        self.assertIn("migration", response.get_json()["issue"][0]["diagnostics"])

    def test_fhir_explorer_shows_setup_notice_before_migration(self):
        self.sign_in()
        with patch("app.fhir.fetch_all", side_effect=missing_table_error()):
            response = self.client.get("/fhir/explorer")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FHIR storage is not set up yet", response.data)
        self.assertIn(b"Existing hospital workflows remain available", response.data)

    def test_patient_booking_waits_for_approval_constraint_migration(self):
        self.sign_in("patient")
        with patch("app.routes._safe_one", return_value=None), \
             patch("app.routes.call_procedure") as book:
            response = self.client.post("/appointments", data={
                "doctor_id": "12",
                "appt_date": "2026-12-01",
                "time_slot": "09:00",
            })
        self.assertEqual(response.status_code, 302)
        book.assert_not_called()


if __name__ == "__main__":
    unittest.main()
