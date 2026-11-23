import unittest
from unittest.mock import patch

from app import create_app


class FHIRWorkspacePreviewTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def sign_in(self, role="chain_admin"):
        with self.client.session_transaction() as state:
            state["login_id"] = 7
            state["role"] = role
            state["staff_id"] = 12
            state["branch_id"] = 1
            state["patient_uhid"] = "AIC0000001"

    def test_staff_patient_registry_shows_separate_fhir_patient_sample(self):
        self.sign_in()
        sample = [{
            "id": "synthea-patient-001",
            "name": "Alex Example",
            "gender": "female",
            "birth_date": "1985-04-12",
            "encounter_count": 3,
        }]
        with patch("app.routes._safe_query", return_value=[]), patch(
            "app.routes._fhir_patient_preview", return_value=sample
        ):
            response = self.client.get("/patients")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FHIR patient samples", response.data)
        self.assertIn(b"Alex Example", response.data)
        self.assertIn(b"synthea-patient-001", response.data)
        self.assertIn(b"not available for hospital booking", response.data)

    def test_staff_appointments_show_encounters_as_history_not_bookable_appointments(self):
        self.sign_in()
        sample = [{
            "resource_id": "encounter-001",
            "patient_fhir_id": "synthea-patient-001",
            "patient_name": "Alex Example",
            "label": "Outpatient visit",
            "status": "finished",
            "event_date": "2025-01-02T10:00:00Z",
        }]
        with patch("app.routes._safe_query", return_value=[]), patch(
            "app.routes._fhir_encounter_preview", return_value=sample
        ):
            response = self.client.get("/appointments")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Historical clinical encounters", response.data)
        self.assertIn(b"Encounter", response.data)
        self.assertIn(b"not bookable Appointment slots", response.data)
        self.assertIn(b"Alex Example", response.data)

    def test_patient_portal_does_not_show_unlinked_synthetic_fhir_records(self):
        self.sign_in("patient")
        with patch("app.routes._safe_query", return_value=[]), patch(
            "app.routes._fhir_patient_preview"
        ) as preview, patch("app.routes._fhir_encounter_preview") as encounter_preview:
            patients_response = self.client.get("/patients")
            appointments_response = self.client.get("/appointments")
        self.assertEqual(patients_response.status_code, 200)
        self.assertEqual(appointments_response.status_code, 200)
        preview.assert_not_called()
        encounter_preview.assert_not_called()
        self.assertNotIn(b"FHIR patient samples", patients_response.data)
        self.assertNotIn(b"Historical clinical encounters", appointments_response.data)


if __name__ == "__main__":
    unittest.main()
