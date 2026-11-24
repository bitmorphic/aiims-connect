import unittest
from unittest.mock import patch

from app import create_app


class ClinicalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def sign_in(self, role="chain_admin", uhid="AIC0000001"):
        with self.client.session_transaction() as state:
            state["login_id"] = 7
            state["role"] = role
            state["staff_id"] = 12
            state["branch_id"] = 1
            state["patient_uhid"] = uhid

    @staticmethod
    def patient():
        return {
            "UHID": "AIC0000001", "Name": "Avery Example",
            "DOB": "1988-02-14", "Gender": "Female",
            "Blood_Group": "O+", "Phone": "9876543210", "Address": "Demo address",
        }

    def test_patient_history_combines_operational_and_fhir_events(self):
        self.sign_in()
        linked = {
            "fhir_patient_id": "synthea-patient-001", "full_name": "Avery Example",
            "gender": "female", "birth_date": "1988-02-14", "phone": None,
            "email": None, "link_note": "Manual verification", "updated_at": "2026-11-24",
        }
        with patch("app.clinical.fetch_one", return_value=self.patient()), \
             patch("app.clinical._clinical_schema_ready", return_value=True), \
             patch("app.clinical._linked_fhir_patient", return_value=linked), \
             patch("app.clinical._operational_timeline", return_value=[{
                 "source": "AIIMS Connect", "resource_type": "Appointment", "resource_id": "12",
                 "event_date": "2026-11-20", "label": "OPD appointment", "status": "Completed",
                 "detail": "Doctor: Demo",
             }]), \
             patch("app.clinical._fhir_timeline", return_value=[{
                 "source": "FHIR R4", "resource_type": "Observation", "resource_id": "obs-1",
                 "event_date": "2026-11-18", "label": "Blood pressure", "status": "final",
                 "detail": "Result: 120 mmHg",
             }]):
            response = self.client.get("/clinical/patients/AIC0000001/history")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Unified clinical timeline", response.data)
        self.assertIn(b"OPD appointment", response.data)
        self.assertIn(b"Blood pressure", response.data)
        self.assertIn(b"AIIMS Connect", response.data)
        self.assertIn(b"FHIR R4", response.data)

    def test_fhir_identity_is_never_guessed_without_a_verified_link(self):
        self.sign_in()
        with patch("app.clinical.fetch_one", return_value=self.patient()), \
             patch("app.clinical._clinical_schema_ready", return_value=True), \
             patch("app.clinical._linked_fhir_patient", return_value=None), \
             patch("app.clinical._operational_timeline", return_value=[]), \
             patch("app.clinical._unlinked_fhir_candidates", return_value=[]):
            response = self.client.get("/clinical/patients/AIC0000001/history?q=Avery")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No FHIR identity linked", response.data)
        self.assertIn(b"No identity is selected automatically", response.data)

    def test_patient_can_only_open_own_clinical_history(self):
        self.sign_in("patient", "AIC0000001")
        with patch("app.clinical.fetch_one", return_value=self.patient()), \
             patch("app.clinical._clinical_schema_ready", return_value=False), \
             patch("app.clinical._operational_timeline", return_value=[]):
            response = self.client.get("/clinical/patients/AIC0000001/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get("/clinical/patients/AIC0000002/history").status_code, 403
        )

    def test_doctor_cannot_open_patient_without_an_existing_appointment_assignment(self):
        self.sign_in("doctor")
        with patch("app.clinical.fetch_one", return_value=None):
            response = self.client.get("/clinical/patients/AIC0000001/history")
        self.assertEqual(response.status_code, 403)

    def test_doctors_cannot_change_patient_identity_links(self):
        self.sign_in("doctor")
        response = self.client.post(
            "/clinical/patients/AIC0000001/link",
            data={"fhir_patient_id": "synthea-patient-001"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
