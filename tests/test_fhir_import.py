import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.import_fhir import inspect_archive, iter_bundle_resources


class FHIRImportParsingTests(unittest.TestCase):
    def test_archive_counts_resources_and_resolves_patient_references(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": "urn:uuid:patient-1",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-1",
                        "gender": "female",
                    },
                },
                {
                    "fullUrl": "urn:uuid:obs-1",
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs-1",
                        "status": "final",
                        "subject": {"reference": "urn:uuid:patient-1"},
                    },
                },
                {
                    "fullUrl": "urn:uuid:practitioner-1",
                    "resource": {
                        "resourceType": "Practitioner",
                        "id": "practitioner-1",
                        "name": [{"family": "Example"}],
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "synthea-sample.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("patient_bundle.json", json.dumps(bundle))

            bundle_count, counts, patients = inspect_archive(archive_path)
            self.assertEqual(bundle_count, 1)
            self.assertEqual(counts["Patient"], 1)
            self.assertEqual(counts["Observation"], 1)
            self.assertEqual(counts["Practitioner"], 1)
            self.assertEqual(patients, {"patient-1"})

            with zipfile.ZipFile(archive_path) as archive:
                info = archive.getinfo("patient_bundle.json")
                rows = list(iter_bundle_resources(archive, info))

        patient_rows = [row for row in rows if row[0] == "Patient"]
        observation_rows = [row for row in rows if row[0] == "Observation"]
        practitioner_rows = [row for row in rows if row[0] == "Practitioner"]
        self.assertEqual(patient_rows[0][2], "patient-1")
        self.assertEqual(observation_rows[0][2], "patient-1")
        self.assertIsNone(practitioner_rows[0][2])

    def test_archive_rejects_non_bundle_json(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "invalid.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("not_bundle.json", json.dumps({"resourceType": "Patient", "id": "p1"}))
            with self.assertRaisesRegex(ValueError, "expected a FHIR Bundle"):
                inspect_archive(archive_path)


if __name__ == "__main__":
    unittest.main()
