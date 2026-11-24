import unittest
from scripts.sync_fhir_tables import _parse_date, _parse_datetime, normalise_patient, normalise_resource, reference_id


class FHIRRelationalProjectionTests(unittest.TestCase):
    def test_preserves_official_fhir_patient_name_and_id(self):
        row = normalise_patient({
            "resourceType": "Patient", "id": "patient-001",
            "name": [{"use": "official", "text": "Avery K. Morgan",
                      "given": ["Avery", "K."], "family": "Morgan"}],
            "birthDate": "1988-02-14", "gender": "female",
            "telecom": [{"system": "phone", "value": "+1 555 0100"}],
        })
        self.assertEqual(row["fhir_patient_id"], "patient-001")
        self.assertEqual(row["full_name"], "Avery K. Morgan")
        self.assertEqual(row["birth_date"].isoformat(), "1988-02-14")
        self.assertEqual(row["phone"], "+1 555 0100")

    def test_builds_name_from_given_and_family_without_changing_case(self):
        row = normalise_patient({
            "resourceType": "Patient", "id": "p-2",
            "name": [{"given": ["Sam", "Lee"], "family": "Taylor"}],
        })
        self.assertEqual(row["full_name"], "Sam Lee Taylor")

    def test_observation_normalizes_coded_value_and_encounter_reference(self):
        row = normalise_resource("Observation", {
            "resourceType": "Observation", "id": "obs-1", "status": "final",
            "encounter": {"reference": "https://example.test/fhir/Encounter/enc-1"},
            "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6",
                                  "display": "Systolic blood pressure"}]},
            "effectiveDateTime": "2026-10-02T10:30:00Z",
            "valueQuantity": {"value": 120, "unit": "mmHg"},
        }, "patient-001")
        self.assertEqual(row["fhir_observation_id"], "obs-1")
        self.assertEqual(row["fhir_patient_id"], "patient-001")
        self.assertEqual(row["fhir_encounter_id"], "enc-1")
        self.assertEqual(row["code"], "8480-6")
        self.assertEqual(str(row["value_numeric"]), "120")
        self.assertEqual(row["value_unit"], "mmHg")

    def test_partial_fhir_date_is_not_fabricated(self):
        self.assertIsNone(_parse_date("1988"))
        self.assertEqual(_parse_date("1988-02-14").isoformat(), "1988-02-14")
        self.assertEqual(_parse_datetime("2026-10-02T10:30:00Z").isoformat(),
                         "2026-10-02T10:30:00")

    def test_reference_resolution_does_not_guess_other_resource_types(self):
        self.assertIsNone(reference_id({"reference": "Practitioner/pr-1"}, "Patient"))
        self.assertEqual(reference_id({"reference": "Patient/p-1"}, "Patient"), "p-1")


if __name__ == "__main__":
    unittest.main()
