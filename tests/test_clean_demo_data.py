import unittest

from scripts.clean_demo_data import apply_cleanup


class RecordingCursor:
    def __init__(self):
        self.statements = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.statements.append((sql, tuple(params)))


class DemoCleanupTests(unittest.TestCase):
    def test_cleanup_deletes_only_demo_linked_ids_and_preserves_fhir(self):
        cursor = RecordingCursor()
        plan = {
            "patient_login_ids": [10],
            "patient_uhids": ["AIC0000001"],
            "staff_ids": [20, 21],
            "staff_login_ids": [11, 12],
            "doctor_ids": [20],
            "referral_ids": [30],
            "appointment_ids": [40, 41],
            "admission_ids": [50],
        }

        apply_cleanup(cursor, plan)
        statements = [sql for sql, _ in cursor.statements]

        self.assertLess(statements.index("DELETE FROM prescription WHERE Appt_ID IN (%s,%s)"),
                        statements.index("DELETE FROM appointment WHERE Appt_ID IN (%s,%s)"))
        self.assertLess(statements.index("DELETE FROM billing WHERE Admission_ID IN (%s)"),
                        statements.index("DELETE FROM admission WHERE Admission_ID IN (%s)"))
        self.assertIn(
            ("UPDATE audit_log SET Actor_Login_ID=NULL WHERE Actor_Login_ID IN (%s,%s,%s)",
             (10, 11, 12)),
            cursor.statements,
        )
        self.assertIn(
            ("DELETE FROM patient WHERE UHID IN (%s)", ("AIC0000001",)),
            cursor.statements,
        )
        self.assertIn(
            ("DELETE FROM staff WHERE Staff_ID IN (%s,%s)", (20, 21)),
            cursor.statements,
        )
        self.assertFalse(any("fhir_resource" in sql for sql in statements))

    def test_empty_plan_executes_no_delete_or_update(self):
        cursor = RecordingCursor()
        empty = {
            "patient_login_ids": [], "patient_uhids": [], "staff_ids": [],
            "staff_login_ids": [], "doctor_ids": [], "referral_ids": [],
            "appointment_ids": [], "admission_ids": [],
        }
        apply_cleanup(cursor, empty)
        self.assertEqual(cursor.statements, [])


if __name__ == "__main__":
    unittest.main()
