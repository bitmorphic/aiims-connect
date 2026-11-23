import unittest
from contextlib import contextmanager
from unittest.mock import patch

import mysql.connector

from app import create_app


class FakeCursor:
    def __init__(self):
        self.rows = None
        self.lastrowid = 0
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "SELECT Branch_ID FROM branch" in sql:
            self.rows = {"Branch_ID": params[0]}
        elif "SELECT Dept_ID FROM department" in sql:
            self.rows = {"Dept_ID": params[0]}
        elif "SELECT Staff_ID FROM staff" in sql:
            self.rows = None
        elif "INSERT INTO staff" in sql:
            self.lastrowid = 501
            self.rows = None
        elif "INSERT INTO doctor" in sql:
            self.rows = None
        else:
            self.rows = None

    def fetchone(self):
        return self.rows


class DoctorRosterAndBookingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def sign_in(self, role="chain_admin", branch=1):
        with self.client.session_transaction() as state:
            state["login_id"] = 7
            state["role"] = role
            state["staff_id"] = 12
            state["branch_id"] = branch
            state["patient_uhid"] = "AIC0000001"

    def test_appointment_page_explains_empty_doctor_roster_and_offers_admin_fix(self):
        self.sign_in("chain_admin")
        with patch("app.routes._safe_query", side_effect=[[], [], []]), patch(
            "app.routes._fhir_encounter_preview", return_value=[]
        ):
            response = self.client.get("/appointments")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No doctors are available for booking yet", response.data)
        self.assertIn(b"Add doctors to roster", response.data)
        self.assertNotIn(b'id="appointment-booking-form"', response.data)

    def test_booking_rejects_doctor_not_present_in_doctor_subtype(self):
        self.sign_in("chain_admin")
        with patch("app.routes._safe_one", return_value=None), patch(
            "app.routes.call_procedure"
        ) as book:
            response = self.client.post("/appointments", data={
                "patient_uhid": "AIC0000001",
                "doctor_id": "999",
                "appt_date": "2026-12-01",
                "time_slot": "09:00",
            })
        self.assertEqual(response.status_code, 302)
        book.assert_not_called()
        with self.client.session_transaction() as state:
            self.assertIn("doctor is no longer on the roster", " ".join(state.get("_flashes", [])[0]))

    def test_availability_endpoint_respects_branch_scope(self):
        self.sign_in("branch_admin", branch=1)
        with patch("app.routes._safe_one", return_value={"Staff_ID": 12, "Branch_ID": 2}):
            response = self.client.get("/appointments/availability?doctor_id=12&date=2026-12-01")
        self.assertEqual(response.status_code, 403)

    def test_availability_endpoint_returns_booked_slots_for_valid_doctor(self):
        self.sign_in("chain_admin")
        with patch("app.routes._safe_one", return_value={"Staff_ID": 12, "Branch_ID": 1}), patch(
            "app.routes._safe_query", return_value=[{"Time_Slot": "09:00"}, {"Time_Slot": "10:30"}]
        ):
            response = self.client.get("/appointments/availability?doctor_id=12&date=2026-12-01")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["booked_slots"], ["09:00", "10:30"])

    def test_doctor_roster_is_not_exposed_to_patient_role(self):
        self.sign_in("patient")
        response = self.client.get("/doctors")
        self.assertEqual(response.status_code, 403)

    def test_branch_admin_can_add_a_doctor_transactionally(self):
        self.sign_in("branch_admin", branch=1)
        fake_cursor = FakeCursor()

        @contextmanager
        def fake_transaction(actor_login_id=None):
            yield None, fake_cursor

        with patch("app.routes.db_transaction", side_effect=fake_transaction):
            response = self.client.post("/doctors", data={
                "name": "Demo Dr. Example",
                "dob": "1982-04-12",
                "phone": "9000000101",
                "dept_id": "22",
                "specialization": "Cardiology",
                "qualification": "MBBS, DM (Cardiology)",
                "consultation_fee": "850",
            })
        self.assertEqual(response.status_code, 302)
        sql_statements = [item[0] for item in fake_cursor.executed]
        self.assertTrue(any("INSERT INTO staff" in sql for sql in sql_statements))
        self.assertTrue(any("INSERT INTO doctor" in sql for sql in sql_statements))


if __name__ == "__main__":
    unittest.main()
