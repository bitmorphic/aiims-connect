import unittest
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from app import create_app


class FakeCursor:
    def __init__(self, affected_rows=1):
        self.affected_rows = affected_rows
        self.procedure_call = None
        self.executed_sql = None
        self.executed_params = None

    def callproc(self, name, args):
        self.procedure_call = (name, args)
        return tuple(args[:-1]) + (1345,)

    def stored_results(self):
        return []

    def execute(self, sql, params):
        self.executed_sql = sql
        self.executed_params = params

    @property
    def rowcount(self):
        return self.affected_rows


class PatientAppointmentAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()
        with self.client.session_transaction() as state:
            state["login_id"] = 7
            state["role"] = "patient"
            state["patient_uhid"] = "AIC0000041"

    def _post_booking(self, affected_rows=1):
        cursor = FakeCursor(affected_rows=affected_rows)
        transaction_state = {"committed": False, "rolled_back": False}

        @contextmanager
        def fake_transaction(_actor_login_id=None):
            try:
                yield None, cursor
            except Exception:
                transaction_state["rolled_back"] = True
                raise
            else:
                transaction_state["committed"] = True

        with patch(
            "app.routes._safe_one",
            side_effect=[
                {"Branch_ID": 5},
                {"CHECK_CLAUSE": "Status IN ('Pending Approval', 'Scheduled', 'Completed', 'Cancelled')"},
            ],
        ), patch("app.routes.db_transaction", side_effect=fake_transaction), patch(
            "app.routes.call_procedure"
        ) as legacy_call:
            response = self.client.post(
                "/appointments",
                data={
                    "doctor_id": "9008",
                    "appt_date": date.today().isoformat(),
                    "time_slot": "10:30",
                },
            )
        legacy_call.assert_not_called()
        return response, cursor, transaction_state

    def test_patient_booking_and_approval_queue_transition_commit_together(self):
        response, cursor, tx = self._post_booking(affected_rows=1)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(cursor.procedure_call[0], "BookAppointment")
        self.assertEqual(cursor.procedure_call[1][0], "AIC0000041")
        self.assertIn("Status='Pending Approval'", cursor.executed_sql)
        self.assertEqual(cursor.executed_params, (1345, "AIC0000041"))
        self.assertTrue(tx["committed"])
        self.assertFalse(tx["rolled_back"])

    def test_failed_approval_transition_rolls_back_the_booking(self):
        response, _cursor, tx = self._post_booking(affected_rows=0)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(tx["rolled_back"])
        self.assertFalse(tx["committed"])


if __name__ == "__main__":
    unittest.main()
