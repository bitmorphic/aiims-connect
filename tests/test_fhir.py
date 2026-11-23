import json
import unittest
from unittest.mock import patch

from app import create_app


class FHIRApiTests(unittest.TestCase):
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

    def test_capability_statement_is_fhir_r4(self):
        response = self.client.get("/fhir/metadata")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("application/fhir+json"))
        payload = response.get_json()
        self.assertEqual(payload["resourceType"], "CapabilityStatement")
        self.assertEqual(payload["fhirVersion"], "4.0.1")
        self.assertIn("Observation", [item["type"] for item in payload["rest"][0]["resource"]])

    def test_resource_read_requires_authentication(self):
        response = self.client.get("/fhir/Patient/synthea-123")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["resourceType"], "OperationOutcome")

    def test_patient_portal_cannot_read_unlinked_synthetic_dataset(self):
        self.sign_in("patient")
        response = self.client.get("/fhir/Patient/synthea-123")
        self.assertEqual(response.status_code, 403)

    def test_staff_can_read_a_resource(self):
        self.sign_in()
        patient = {"resourceType": "Patient", "id": "synthea-123", "gender": "female"}
        with patch("app.fhir.fetch_one", return_value={"payload": json.dumps(patient)}):
            response = self.client.get("/fhir/Patient/synthea-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), patient)

    def test_search_returns_fhir_searchset_bundle(self):
        self.sign_in()
        patient = {"resourceType": "Patient", "id": "synthea-123", "gender": "female"}
        count = {"total": 1}
        rows = [{"resource_id": "synthea-123", "payload": json.dumps(patient)}]
        with patch("app.fhir.fetch_one", return_value=count), patch("app.fhir.fetch_all", return_value=rows):
            response = self.client.get("/fhir/Patient?gender=female")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["resourceType"], "Bundle")
        self.assertEqual(payload["type"], "searchset")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["entry"][0]["resource"]["id"], "synthea-123")

    def test_unsupported_search_parameter_returns_operation_outcome(self):
        self.sign_in()
        response = self.client.get("/fhir/Patient?sort=name")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["resourceType"], "OperationOutcome")

    def test_search_rejects_invalid_page_size(self):
        self.sign_in()
        response = self.client.get("/fhir/Patient?_count=1000")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
