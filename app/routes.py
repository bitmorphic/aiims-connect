from datetime import date, datetime, time, timedelta
from functools import wraps
import logging

import bcrypt
import mysql.connector
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)

from .db import call_procedure, execute, fetch_all, fetch_one

bp = Blueprint("main", __name__)
log = logging.getLogger(__name__)

ROLE_LABELS = {
    "chain_admin": "Chain administrator",
    "branch_admin": "Branch administrator",
    "doctor": "Doctor",
    "receptionist": "Receptionist",
    "patient": "Patient",
}


def role_from_record(row):
    role = (row.get("Role") or "").strip().lower()
    if role == "admin":
        level = (row.get("Access_Level") or "Branch").strip().lower()
        return "chain_admin" if level == "chain" else "branch_admin"
    if role in ("doctor", "receptionist", "patient"):
        return role
    return "patient"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("login_id"):
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def actor_id():
    return session.get("login_id")


def is_branch_scoped():
    return session.get("role") in ("branch_admin", "receptionist", "doctor")


def branch_id():
    return session.get("branch_id")


def _safe_query(sql, params=()):
    try:
        return fetch_all(sql, params)
    except mysql.connector.Error:
        current_app.logger.exception("Database read failed")
        raise


def _safe_one(sql, params=()):
    try:
        return fetch_one(sql, params)
    except mysql.connector.Error:
        current_app.logger.exception("Database read failed")
        raise


def _time_slot_is_valid(value):
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    if parsed.second != 0 or parsed.minute not in (0, 30):
        return False
    morning = time(9, 0) <= parsed <= time(12, 30)
    afternoon = time(14, 0) <= parsed <= time(16, 30)
    return morning or afternoon


def _appointments_for_role():
    role = session.get("role")
    if role == "patient":
        return " WHERE Patient_UHID = %s", (session.get("patient_uhid"),)
    if role == "doctor":
        return " WHERE Doctor_ID = %s", (session.get("staff_id"),)
    if role in ("branch_admin", "receptionist"):
        return " WHERE Branch_ID = %s", (branch_id(),)
    return "", ()


def _scope_admission(admission_id):
    row = _safe_one(
        """SELECT a.Admission_ID, a.Patient_UHID, a.Ward_ID, a.Discharge_Date,
                  w.Branch_ID
           FROM admission a JOIN ward w ON w.Ward_ID = a.Ward_ID
           WHERE a.Admission_ID = %s""",
        (admission_id,),
    )
    if not row:
        abort(404)
    role = session.get("role")
    if role == "patient" and row["Patient_UHID"] != session.get("patient_uhid"):
        abort(403)
    if role in ("branch_admin", "receptionist", "doctor") and row["Branch_ID"] != branch_id():
        abort(403)
    return row


@bp.route("/")
def home():
    if session.get("login_id"):
        return redirect(url_for("main.dashboard"))
    stats = {"branches": 0, "departments": 0, "doctors": 0, "wards": 0}
    try:
        counts = _safe_one(
            """SELECT
                 (SELECT COUNT(*) FROM branch) AS branches,
                 (SELECT COUNT(*) FROM department) AS departments,
                 (SELECT COUNT(*) FROM doctor) AS doctors,
                 (SELECT COUNT(*) FROM ward) AS wards"""
        )
        if counts:
            stats.update(counts)
        branches = _safe_query(
            "SELECT Branch_Name, City FROM branch ORDER BY Is_Main DESC, Branch_Name"
        )
    except mysql.connector.Error:
        current_app.logger.exception("Landing page could not load live network totals")
        branches = []
    return render_template("landing.html", stats=stats, branches=branches)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("login_id"):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            row = _safe_one(
                """SELECT l.Login_ID, l.Username, l.Password_Hash, l.Role, l.Is_Active,
                          l.Staff_ID, l.Patient_UHID,
                          s.Name AS Staff_Name, s.Branch_ID, s.Staff_Type,
                          a.Access_Level, p.Name AS Patient_Name
                   FROM login l
                   LEFT JOIN staff s ON s.Staff_ID = l.Staff_ID
                   LEFT JOIN admin_staff a ON a.Staff_ID = s.Staff_ID
                   LEFT JOIN patient p ON p.UHID = l.Patient_UHID
                   WHERE l.Username = %s LIMIT 1""",
                (username,),
            )
        except mysql.connector.Error:
            current_app.logger.exception("Login database lookup failed")
            flash("The database is not reachable. Check the app's DB connection settings.", "danger")
            return render_template("login.html")

        valid = False
        if row and row["Is_Active"]:
            try:
                valid = bcrypt.checkpw(password.encode("utf-8"), row["Password_Hash"].encode("utf-8"))
            except (ValueError, TypeError):
                valid = False

        if valid:
            session.clear()
            session.permanent = True
            role = role_from_record(row)
            session.update(
                login_id=row["Login_ID"],
                username=row["Username"],
                role=role,
                role_label=ROLE_LABELS.get(role, role.title()),
                staff_id=row["Staff_ID"],
                branch_id=row["Branch_ID"],
                patient_uhid=row["Patient_UHID"],
                display_name=row["Staff_Name"] or row["Patient_Name"] or row["Username"],
            )
            return redirect(url_for("main.dashboard"))

        flash("Username or password is incorrect, or the account is inactive.", "danger")

    return render_template("login.html")


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.home"))


@bp.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]
    params = ()
    patient_filter = ""
    appointment_filter = ""
    admission_filter = ""
    referral_filter = ""

    if role == "patient":
        patient_filter = " WHERE UHID = %s"
        appointment_filter = " WHERE Patient_UHID = %s"
        admission_filter = " WHERE a.Patient_UHID = %s"
        referral_filter = " WHERE Patient_UHID = %s"
        params = (session["patient_uhid"],)
    elif role == "doctor":
        appointment_filter = " WHERE Doctor_ID = %s"
        admission_filter = " WHERE w.Branch_ID = %s"
        referral_filter = " WHERE Initiator_Staff_ID = %s"
    elif role in ("branch_admin", "receptionist"):
        appointment_filter = " WHERE Branch_ID = %s"
        admission_filter = " WHERE w.Branch_ID = %s"
        referral_filter = " WHERE Source_Branch_ID = %s OR Dest_Branch_ID = %s"

    if role == "patient":
        patients_count = 1
        appointments_count = _safe_one("SELECT COUNT(*) AS n FROM appointment WHERE Patient_UHID = %s", params)["n"]
        admissions_count = _safe_one("SELECT COUNT(*) AS n FROM admission WHERE Patient_UHID = %s AND Discharge_Date IS NULL", params)["n"]
        referrals_count = _safe_one("SELECT COUNT(*) AS n FROM referral WHERE Patient_UHID = %s", params)["n"]
    elif role == "doctor":
        staff_id = session["staff_id"]
        patients_count = _safe_one("SELECT COUNT(DISTINCT Patient_UHID) AS n FROM appointment WHERE Doctor_ID = %s", (staff_id,))["n"]
        appointments_count = _safe_one("SELECT COUNT(*) AS n FROM appointment WHERE Doctor_ID = %s", (staff_id,))["n"]
        admissions_count = _safe_one("SELECT COUNT(*) AS n FROM admission a JOIN ward w ON w.Ward_ID=a.Ward_ID WHERE w.Branch_ID=%s AND a.Discharge_Date IS NULL", (branch_id(),))["n"]
        referrals_count = _safe_one("SELECT COUNT(*) AS n FROM referral WHERE Initiator_Staff_ID=%s", (staff_id,))["n"]
    elif role in ("branch_admin", "receptionist"):
        bid = branch_id()
        patients_count = _safe_one(
            """SELECT COUNT(DISTINCT Patient_UHID) AS n FROM (
                 SELECT a.Patient_UHID FROM appointment a WHERE a.Branch_ID=%s
                 UNION SELECT ad.Patient_UHID FROM admission ad JOIN ward w ON w.Ward_ID=ad.Ward_ID WHERE w.Branch_ID=%s
               ) scoped_patients""", (bid, bid)
        )["n"]
        appointments_count = _safe_one("SELECT COUNT(*) AS n FROM appointment WHERE Branch_ID=%s", (bid,))["n"]
        admissions_count = _safe_one("SELECT COUNT(*) AS n FROM admission a JOIN ward w ON w.Ward_ID=a.Ward_ID WHERE w.Branch_ID=%s AND a.Discharge_Date IS NULL", (bid,))["n"]
        referrals_count = _safe_one("SELECT COUNT(*) AS n FROM referral WHERE Source_Branch_ID=%s OR Dest_Branch_ID=%s", (bid, bid))["n"]
    else:
        patients_count = _safe_one("SELECT COUNT(*) AS n FROM patient")["n"]
        appointments_count = _safe_one("SELECT COUNT(*) AS n FROM appointment")["n"]
        admissions_count = _safe_one("SELECT COUNT(*) AS n FROM admission WHERE Discharge_Date IS NULL")["n"]
        referrals_count = _safe_one("SELECT COUNT(*) AS n FROM referral WHERE Status='Pending'")["n"]

    if role == "chain_admin":
        branches = _safe_query("SELECT * FROM chain_occupancy_view ORDER BY Branch_Name")
        recent = _safe_query("SELECT * FROM doctor_schedule_view ORDER BY Appt_Date DESC, Time_Slot DESC LIMIT 8")
    elif role == "patient":
        branches = _safe_query("SELECT * FROM chain_occupancy_view ORDER BY Branch_Name")
        recent = _safe_query(
            "SELECT * FROM doctor_schedule_view WHERE Patient_UHID=%s ORDER BY Appt_Date DESC, Time_Slot DESC LIMIT 8",
            (session["patient_uhid"],),
        )
    elif role == "doctor":
        branches = _safe_query("SELECT * FROM chain_occupancy_view WHERE Branch_ID=%s", (branch_id(),))
        recent = _safe_query(
            "SELECT * FROM doctor_schedule_view WHERE Doctor_ID=%s ORDER BY Appt_Date DESC, Time_Slot DESC LIMIT 8",
            (session["staff_id"],),
        )
    else:
        branches = _safe_query("SELECT * FROM chain_occupancy_view WHERE Branch_ID=%s", (branch_id(),))
        recent = _safe_query(
            "SELECT * FROM doctor_schedule_view WHERE Branch_ID=%s ORDER BY Appt_Date DESC, Time_Slot DESC LIMIT 8",
            (branch_id(),),
        )

    stats = {
        "patients": patients_count,
        "appointments": appointments_count,
        "admissions": admissions_count,
        "referrals": referrals_count,
    }
    return render_template("dashboard.html", stats=stats, branches=branches, recent=recent)


@bp.route("/patients", methods=["GET", "POST"])
@login_required
def patients():
    role = session["role"]
    if request.method == "POST":
        if role not in ("chain_admin", "branch_admin", "receptionist"):
            abort(403)
        form = request.form
        username = form.get("username", "").strip()
        password = form.get("password", "")
        if len(username) < 4 or len(password) < 8:
            flash("Patient login username must be at least 4 characters and password at least 8.", "warning")
            return redirect(url_for("main.patients"))
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            uhid = call_procedure(
                "RegisterPatient",
                (
                    form.get("name", "").strip(),
                    form.get("dob"),
                    form.get("gender"),
                    form.get("blood_group") or None,
                    form.get("phone", "").strip(),
                    form.get("address", "").strip(),
                    username,
                    password_hash,
                ),
                actor_login_id=actor_id(),
                returns_output=True,
            )
            flash("Patient registered successfully. UHID: " + str(uhid), "success")
        except mysql.connector.Error as exc:
            current_app.logger.exception("Patient registration failed")
            flash(getattr(exc, "msg", "Patient registration failed. Check the submitted details."), "danger")
        return redirect(url_for("main.patients"))

    q = request.args.get("q", "").strip()
    if role == "patient":
        sql = "SELECT * FROM patient_self_view WHERE UHID=%s"
        rows = _safe_query(sql, (session["patient_uhid"],))
    else:
        sql = """SELECT p.UHID,p.Name,p.DOB,p.Gender,p.Blood_Group,p.Phone,p.Address,
                        p.Created_At,l.Username
                 FROM patient p LEFT JOIN login l ON l.Patient_UHID=p.UHID"""
        params = ()
        if role == "doctor":
            sql += " WHERE EXISTS (SELECT 1 FROM appointment ap WHERE ap.Patient_UHID=p.UHID AND ap.Doctor_ID=%s)"
            params = (session["staff_id"],)
        if q:
            sql += (" AND " if params else " WHERE ") + "(p.UHID LIKE %s OR p.Name LIKE %s OR p.Phone LIKE %s)"
            params += (f"%{q}%", f"%{q}%", f"%{q}%")
        sql += " ORDER BY p.Created_At DESC LIMIT 200"
        rows = _safe_query(sql, params)
    can_create = role in ("chain_admin", "branch_admin", "receptionist")
    return render_template(
        "table.html", title="Patient registry", eyebrow="PATIENT SERVICES",
        subtitle="A single UHID connects patient activity across the hospital network.",
        rows=rows, kind="patients", q=q, can_create=can_create,
    )


@bp.route("/appointments", methods=["GET", "POST"])
@login_required
def appointments():
    role = session["role"]
    can_create = role in ("chain_admin", "branch_admin", "receptionist", "patient")
    if request.method == "POST":
        if not can_create:
            abort(403)
        patient_uhid = session["patient_uhid"] if role == "patient" else request.form.get("patient_uhid")
        doctor_id = request.form.get("doctor_id")
        appt_date = request.form.get("appt_date")
        time_slot = request.form.get("time_slot")
        if not patient_uhid or not doctor_id or not appt_date or not _time_slot_is_valid(time_slot):
            flash("Choose a patient, doctor, future date and a valid 30-minute OPD slot.", "warning")
            return redirect(url_for("main.appointments"))
        try:
            appt_id = call_procedure(
                "BookAppointment",
                (patient_uhid, int(doctor_id), appt_date, time_slot, None),
                actor_login_id=actor_id(),
                returns_output=True,
            )
            flash("Appointment booked successfully. Appointment ID: " + str(appt_id), "success")
        except mysql.connector.Error as exc:
            current_app.logger.exception("Appointment booking failed")
            flash(getattr(exc, "msg", "Appointment could not be booked. Try another slot."), "danger")
        return redirect(url_for("main.appointments"))

    clause, params = _appointments_for_role()
    sql = "SELECT * FROM doctor_schedule_view" + clause + " ORDER BY Appt_Date DESC, Time_Slot DESC LIMIT 250"
    rows = _safe_query(sql, params)
    patients_list = []
    if role in ("chain_admin", "branch_admin", "receptionist"):
        patients_list = _safe_query("SELECT UHID,Name FROM patient ORDER BY Name LIMIT 250")
    doctors = _safe_query(
        """SELECT d.Staff_ID,s.Name,d.Specialization,s.Branch_ID,b.Branch_Name
           FROM doctor d JOIN staff s ON s.Staff_ID=d.Staff_ID
           JOIN branch b ON b.Branch_ID=s.Branch_ID
           ORDER BY b.Branch_Name,s.Name"""
    )
    return render_template(
        "table.html", title="Appointments", eyebrow="OUTPATIENT DEPARTMENT",
        subtitle="Book and manage OPD visits with database-enforced slot and token rules.",
        rows=rows, kind="appointments", q=request.args.get("q", ""),
        can_create=can_create, patients=patients_list, doctors=doctors,
    )


@bp.post("/appointments/<int:appt_id>/cancel")
@login_required
def cancel_appointment(appt_id):
    row = _safe_one("SELECT Patient_UHID,Doctor_ID,Branch_ID,Status FROM appointment WHERE Appt_ID=%s", (appt_id,))
    if not row:
        abort(404)
    role = session["role"]
    allowed = (
        role == "chain_admin"
        or (role == "branch_admin" and row["Branch_ID"] == branch_id())
        or (role == "receptionist" and row["Branch_ID"] == branch_id())
        or (role == "doctor" and row["Doctor_ID"] == session["staff_id"])
        or (role == "patient" and row["Patient_UHID"] == session["patient_uhid"])
    )
    if not allowed:
        abort(403)
    try:
        call_procedure("CancelAppointment", (appt_id,), actor_login_id=actor_id())
        flash("Appointment cancelled.", "success")
    except mysql.connector.Error as exc:
        flash(getattr(exc, "msg", "Appointment could not be cancelled."), "danger")
    return redirect(url_for("main.appointments"))


@bp.post("/appointments/<int:appt_id>/complete")
@login_required
def complete_appointment(appt_id):
    row = _safe_one("SELECT Doctor_ID,Branch_ID,Status FROM appointment WHERE Appt_ID=%s", (appt_id,))
    if not row:
        abort(404)
    role = session["role"]
    allowed = (
        role == "chain_admin"
        or (role == "branch_admin" and row["Branch_ID"] == branch_id())
        or (role == "receptionist" and row["Branch_ID"] == branch_id())
        or (role == "doctor" and row["Doctor_ID"] == session["staff_id"])
    )
    if not allowed:
        abort(403)
    try:
        call_procedure("CompleteAppointment", (appt_id,), actor_login_id=actor_id())
        flash("Appointment marked as completed.", "success")
    except mysql.connector.Error as exc:
        flash(getattr(exc, "msg", "Appointment could not be completed."), "danger")
    return redirect(url_for("main.appointments"))


@bp.route("/wards")
@login_required
def wards():
    role = session["role"]
    sql = "SELECT * FROM branch_ward_view"
    params = ()
    if role in ("branch_admin", "receptionist", "doctor"):
        sql += " WHERE Branch_ID=%s"
        params = (branch_id(),)
    rows = _safe_query(sql + " ORDER BY Branch_Name,Ward_Name", params)
    return render_template(
        "table.html", title="Ward & bed availability", eyebrow="INPATIENT CAPACITY",
        subtitle="Live bed availability is maintained by database triggers.",
        rows=rows, kind="wards", can_create=False,
    )


@bp.route("/admissions", methods=["GET", "POST"])
@login_required
def admissions():
    role = session["role"]
    can_create = role in ("chain_admin", "branch_admin", "receptionist")
    if request.method == "POST":
        if not can_create:
            abort(403)
        ward_id = request.form.get("ward_id")
        patient_uhid = request.form.get("patient_uhid")
        if not ward_id or not patient_uhid:
            flash("Choose a patient and ward.", "warning")
            return redirect(url_for("main.admissions"))
        ward = _safe_one("SELECT Branch_ID FROM ward WHERE Ward_ID=%s", (ward_id,))
        if not ward:
            abort(404)
        if role in ("branch_admin", "receptionist") and ward["Branch_ID"] != branch_id():
            abort(403)
        try:
            admission_id = call_procedure(
                "AdmitPatient",
                (
                    patient_uhid, int(ward_id),
                    request.form.get("attendant_name", "").strip(),
                    request.form.get("attendant_phone", "").strip(),
                ),
                actor_login_id=actor_id(),
                returns_output=True,
            )
            flash("Patient admitted. Admission ID: " + str(admission_id), "success")
        except mysql.connector.Error as exc:
            flash(getattr(exc, "msg", "Admission could not be completed."), "danger")
        return redirect(url_for("main.admissions"))

    sql = """SELECT a.Admission_ID,a.Patient_UHID,p.Name AS Patient_Name,
                    w.Ward_Name,w.Ward_Type,b.Branch_Name,w.Branch_ID,
                    a.Admit_Date,a.Discharge_Date,
                    CASE WHEN a.Discharge_Date IS NULL THEN 'Active' ELSE 'Discharged' END AS Status
             FROM admission a JOIN patient p ON p.UHID=a.Patient_UHID
             JOIN ward w ON w.Ward_ID=a.Ward_ID JOIN branch b ON b.Branch_ID=w.Branch_ID"""
    params = ()
    if role == "patient":
        sql += " WHERE a.Patient_UHID=%s"
        params = (session["patient_uhid"],)
    elif role in ("branch_admin", "receptionist", "doctor"):
        sql += " WHERE w.Branch_ID=%s"
        params = (branch_id(),)
    rows = _safe_query(sql + " ORDER BY a.Admit_Date DESC LIMIT 200", params)

    patients_list = []
    wards_list = []
    if can_create:
        patients_list = _safe_query("SELECT UHID,Name FROM patient ORDER BY Name LIMIT 250")
        wards_list = _safe_query("SELECT Ward_ID,Ward_Name,Ward_Type,Available_Beds,Branch_ID FROM ward WHERE Available_Beds>0 ORDER BY Branch_ID,Ward_Name")
        if role in ("branch_admin", "receptionist"):
            wards_list = [w for w in wards_list if w["Branch_ID"] == branch_id()]
    return render_template(
        "table.html", title="Admissions & discharge", eyebrow="INPATIENT CARE",
        subtitle="Admission and discharge procedures update ward capacity and billing atomically.",
        rows=rows, kind="admissions", can_create=can_create,
        patients=patients_list, wards=wards_list,
    )


@bp.post("/admissions/<int:admission_id>/discharge")
@login_required
def discharge_admission(admission_id):
    if session["role"] not in ("chain_admin", "branch_admin", "receptionist"):
        abort(403)
    row = _scope_admission(admission_id)
    if row["Discharge_Date"] is not None:
        flash("This admission has already been discharged.", "warning")
        return redirect(url_for("main.admissions"))
    try:
        bill_id = call_procedure(
            "DischargePatient",
            (
                admission_id,
                float(request.form.get("consultation_fee") or 0),
                float(request.form.get("medicine_charges") or 0),
            ),
            actor_login_id=actor_id(),
            returns_output=True,
        )
        flash("Discharge completed and bill generated. Bill ID: " + str(bill_id), "success")
    except (mysql.connector.Error, ValueError) as exc:
        current_app.logger.exception("Discharge failed")
        flash(getattr(exc, "msg", "Discharge could not be completed. Check the charges."), "danger")
    return redirect(url_for("main.admissions"))


@bp.route("/referrals", methods=["GET", "POST"])
@login_required
def referrals():
    role = session["role"]
    can_create = role == "doctor"
    if request.method == "POST":
        if not can_create:
            abort(403)
        dest = request.form.get("dest_branch_id")
        patient_uhid = request.form.get("patient_uhid")
        reason = request.form.get("reason", "").strip()
        if not dest or not patient_uhid or len(reason) < 5:
            flash("Choose a patient, destination branch and a reason of at least five characters.", "warning")
            return redirect(url_for("main.referrals"))
        if int(dest) == int(branch_id()):
            flash("A referral must go to a different branch.", "warning")
            return redirect(url_for("main.referrals"))
        try:
            execute(
                """INSERT INTO referral
                   (Patient_UHID,Initiator_Staff_ID,Source_Branch_ID,Dest_Branch_ID,Reason,Status)
                   VALUES(%s,%s,%s,%s,%s,'Pending')""",
                (patient_uhid, session["staff_id"], branch_id(), int(dest), reason),
                actor_login_id=actor_id(),
            )
            flash("Inter-branch referral created.", "success")
        except mysql.connector.Error as exc:
            current_app.logger.exception("Referral creation failed")
            flash(getattr(exc, "msg", "Referral could not be created."), "danger")
        return redirect(url_for("main.referrals"))

    sql = "SELECT * FROM referral_flow_view"
    params = ()
    if role == "patient":
        sql += " WHERE Patient_UHID=%s"
        params = (session["patient_uhid"],)
    elif role == "doctor":
        sql += " WHERE Initiator_Staff_ID=%s"
        params = (session["staff_id"],)
    elif role in ("branch_admin", "receptionist"):
        sql += " WHERE Source_Branch_ID=%s OR Dest_Branch_ID=%s"
        params = (branch_id(), branch_id())
    rows = _safe_query(sql + " ORDER BY Created_At DESC LIMIT 200", params)

    patients_list = []
    branches = []
    if can_create:
        patients_list = _safe_query("SELECT UHID,Name FROM patient ORDER BY Name LIMIT 250")
        branches = _safe_query("SELECT Branch_ID,Branch_Name FROM branch WHERE Branch_ID<>%s ORDER BY Branch_Name", (branch_id(),))
    destination_doctors = _safe_query(
        """SELECT d.Staff_ID,s.Name,s.Branch_ID,b.Branch_Name
           FROM doctor d JOIN staff s ON s.Staff_ID=d.Staff_ID
           JOIN branch b ON b.Branch_ID=s.Branch_ID ORDER BY b.Branch_Name,s.Name"""
    )
    can_process = role in ("chain_admin", "branch_admin", "receptionist")
    return render_template(
        "table.html", title="Inter-branch referrals", eyebrow="NETWORK COORDINATION",
        subtitle="Move a referral through pending, accepted, rejected and completed states.",
        rows=rows, kind="referrals", can_create=can_create, can_process=can_process,
        patients=patients_list, branches=branches, doctors=destination_doctors,
    )


@bp.post("/referrals/<int:referral_id>/accept")
@login_required
def accept_referral(referral_id):
    if session["role"] not in ("chain_admin", "branch_admin", "receptionist"):
        abort(403)
    row = _safe_one("SELECT Dest_Branch_ID,Status FROM referral WHERE Referral_ID=%s", (referral_id,))
    if not row:
        abort(404)
    if session["role"] in ("branch_admin", "receptionist") and row["Dest_Branch_ID"] != branch_id():
        abort(403)
    try:
        appt_id = call_procedure(
            "AcceptReferral",
            (
                referral_id, int(request.form.get("doctor_id")),
                request.form.get("appt_date"), request.form.get("time_slot"),
            ),
            actor_login_id=actor_id(),
            returns_output=True,
        )
        flash("Referral accepted and appointment created. Appointment ID: " + str(appt_id), "success")
    except (mysql.connector.Error, TypeError, ValueError) as exc:
        flash(getattr(exc, "msg", "Referral could not be accepted. Check doctor and OPD slot."), "danger")
    return redirect(url_for("main.referrals"))


@bp.post("/referrals/<int:referral_id>/reject")
@login_required
def reject_referral(referral_id):
    if session["role"] not in ("chain_admin", "branch_admin", "receptionist"):
        abort(403)
    row = _safe_one("SELECT Dest_Branch_ID FROM referral WHERE Referral_ID=%s", (referral_id,))
    if not row:
        abort(404)
    if session["role"] in ("branch_admin", "receptionist") and row["Dest_Branch_ID"] != branch_id():
        abort(403)
    try:
        call_procedure("RejectReferral", (referral_id,), actor_login_id=actor_id())
        flash("Referral rejected.", "success")
    except mysql.connector.Error as exc:
        flash(getattr(exc, "msg", "Referral could not be rejected."), "danger")
    return redirect(url_for("main.referrals"))


@bp.route("/prescriptions", methods=["GET", "POST"])
@login_required
def prescriptions():
    role = session["role"]
    if request.method == "POST":
        if role != "doctor":
            abort(403)
        appt_id = request.form.get("appt_id")
        try:
            prescription_id = call_procedure(
                "CreatePrescription",
                (
                    int(appt_id), request.form.get("medicine_name", "").strip(),
                    request.form.get("dosage", "").strip(), request.form.get("notes", "").strip() or None,
                ),
                actor_login_id=actor_id(),
                returns_output=True,
            )
            flash("Prescription saved. Prescription ID: " + str(prescription_id), "success")
        except (mysql.connector.Error, TypeError, ValueError) as exc:
            flash(getattr(exc, "msg", "Prescription could not be saved."), "danger")
        return redirect(url_for("main.prescriptions"))

    sql = """SELECT pr.Prescription_ID,pr.Appt_ID,a.Patient_UHID,p.Name AS Patient_Name,
                    pr.Medicine_Name,pr.Dosage,pr.Notes,pr.Created_At,
                    d.Staff_ID AS Doctor_ID,s.Name AS Doctor_Name,b.Branch_Name
             FROM prescription pr JOIN appointment a ON a.Appt_ID=pr.Appt_ID
             JOIN patient p ON p.UHID=a.Patient_UHID
             JOIN doctor d ON d.Staff_ID=a.Doctor_ID JOIN staff s ON s.Staff_ID=d.Staff_ID
             JOIN branch b ON b.Branch_ID=a.Branch_ID"""
    params = ()
    if role == "patient":
        sql += " WHERE a.Patient_UHID=%s"
        params = (session["patient_uhid"],)
    elif role == "doctor":
        sql += " WHERE a.Doctor_ID=%s"
        params = (session["staff_id"],)
    elif role in ("branch_admin", "receptionist"):
        sql += " WHERE a.Branch_ID=%s"
        params = (branch_id(),)
    rows = _safe_query(sql + " ORDER BY pr.Created_At DESC LIMIT 200", params)
    appointments_list = []
    if role == "doctor":
        appointments_list = _safe_query(
            """SELECT Appt_ID,Appt_Date,Time_Slot,Patient_UHID,Patient_Name
               FROM doctor_schedule_view WHERE Doctor_ID=%s AND Status<>'Cancelled'
               ORDER BY Appt_Date DESC,Time_Slot DESC LIMIT 100""",
            (session["staff_id"],),
        )
    return render_template(
        "table.html", title="Prescriptions", eyebrow="CLINICAL RECORDS",
        subtitle="Prescription records are linked to appointments and patient UHIDs.",
        rows=rows, kind="prescriptions", can_create=(role == "doctor"),
        appointments=appointments_list,
    )


@bp.route("/billing")
@login_required
def billing():
    role = session["role"]
    sql = """SELECT bi.Bill_ID,bi.Admission_ID,a.Patient_UHID,p.Name AS Patient_Name,
                    b.Branch_Name,bi.Consultation_Fee,bi.Room_Charges,bi.Medicine_Charges,
                    bi.Total,bi.Status,bi.Generated_At,bi.Paid_At,w.Branch_ID
             FROM billing bi JOIN admission a ON a.Admission_ID=bi.Admission_ID
             JOIN patient p ON p.UHID=a.Patient_UHID
             JOIN ward w ON w.Ward_ID=a.Ward_ID JOIN branch b ON b.Branch_ID=w.Branch_ID"""
    params = ()
    if role == "patient":
        sql += " WHERE a.Patient_UHID=%s"
        params = (session["patient_uhid"],)
    elif role == "doctor":
        sql += " WHERE 1=0"
    elif role in ("branch_admin", "receptionist"):
        sql += " WHERE w.Branch_ID=%s"
        params = (branch_id(),)
    rows = _safe_query(sql + " ORDER BY bi.Generated_At DESC LIMIT 200", params)
    return render_template(
        "table.html", title="Billing & payments", eyebrow="REVENUE MANAGEMENT",
        subtitle="Bills are generated by the discharge procedure and totals are computed in MySQL.",
        rows=rows, kind="billing", can_create=False,
    )


@bp.post("/billing/<int:bill_id>/pay")
@login_required
def mark_bill_paid(bill_id):
    if session["role"] not in ("chain_admin", "branch_admin", "receptionist"):
        abort(403)
    bill = _safe_one(
        """SELECT bi.Bill_ID,w.Branch_ID FROM billing bi
           JOIN admission a ON a.Admission_ID=bi.Admission_ID
           JOIN ward w ON w.Ward_ID=a.Ward_ID WHERE bi.Bill_ID=%s""",
        (bill_id,),
    )
    if not bill:
        abort(404)
    if session["role"] in ("branch_admin", "receptionist") and bill["Branch_ID"] != branch_id():
        abort(403)
    try:
        call_procedure("MarkBillPaid", (bill_id,), actor_login_id=actor_id())
        flash("Bill marked as paid.", "success")
    except mysql.connector.Error as exc:
        flash(getattr(exc, "msg", "Payment status could not be updated."), "danger")
    return redirect(url_for("main.billing"))


@bp.route("/my-records")
@roles_required("patient")
def my_records():
    rows = _safe_query(
        "SELECT * FROM patient_history_view WHERE UHID=%s ORDER BY Event_Date DESC,Record_ID DESC",
        (session["patient_uhid"],),
    )
    return render_template(
        "table.html", title="My care history", eyebrow="PATIENT PORTAL",
        subtitle="Appointments and admissions associated with your hospital-wide UHID.",
        rows=rows, kind="history", can_create=False,
    )


@bp.route("/reports")
@roles_required("chain_admin", "branch_admin")
def reports():
    if session["role"] == "chain_admin":
        revenue = _safe_query("SELECT * FROM branch_revenue_view ORDER BY Branch_Name")
        occupancy = _safe_query("SELECT * FROM chain_occupancy_view ORDER BY Branch_Name")
    else:
        revenue = _safe_query("SELECT * FROM branch_revenue_view WHERE Branch_ID=%s", (branch_id(),))
        occupancy = _safe_query("SELECT * FROM chain_occupancy_view WHERE Branch_ID=%s", (branch_id(),))
    return render_template("reports.html", revenue=revenue, occupancy=occupancy)


@bp.app_errorhandler(403)
def forbidden(error):
    return render_template("error.html", code=403, message="Your account does not have permission to access this section."), 403


@bp.app_errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="The requested page or record could not be found."), 404


@bp.app_errorhandler(500)
def internal_error(error):
    current_app.logger.exception("Unhandled application error")
    return render_template("error.html", code=500, message="Something went wrong. Check the application logs for details."), 500
