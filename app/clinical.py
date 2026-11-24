"""Unified AIIMS operational and FHIR clinical-history workflow."""
from datetime import date, datetime
import logging

import mysql.connector
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .db import connect, execute, fetch_all, fetch_one

bp = Blueprint("clinical", __name__, url_prefix="/clinical")
log = logging.getLogger(__name__)
STAFF_ROLES = {"chain_admin", "branch_admin", "receptionist", "doctor"}
LINK_ROLES = {"chain_admin", "branch_admin", "receptionist"}
FHIR_TABLES = {
    "fhir_patient", "fhir_patient_link", "fhir_encounter", "fhir_observation",
    "fhir_condition", "fhir_procedure", "fhir_medication_request",
}


def _guard_patient_access(uhid):
    if not session.get("login_id"):
        return redirect(url_for("main.login", portal="staff", next=request.path))
    role = session.get("role")
    if role == "patient":
        if session.get("patient_uhid") != uhid:
            abort(403)
        return None
    if role not in STAFF_ROLES:
        abort(403)
    if role == "doctor":
        assigned = fetch_one(
            "SELECT 1 AS allowed FROM appointment WHERE Patient_UHID=%s AND Doctor_ID=%s LIMIT 1",
            (uhid, session.get("staff_id")),
        )
        if not assigned:
            abort(403)
    return None


def _clinical_schema_ready():
    placeholders = ",".join(["%s"] * len(FHIR_TABLES))
    rows = fetch_all(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (" + placeholders + ")",
        tuple(sorted(FHIR_TABLES)),
    )
    return FHIR_TABLES.issubset({row["TABLE_NAME"] for row in rows})


def _iso(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _operational_timeline(uhid):
    """Read the actual hospital workflow events associated with one UHID."""
    records = []
    queries = [
        ("Appointment", """SELECT a.Appt_ID id,a.Appt_Date event_date,
             CONCAT('OPD appointment · ',TIME_FORMAT(a.Time_Slot,'%H:%i')) label,
             a.Status status,CONCAT_WS(' · ',CONCAT('Doctor: ',COALESCE(s.Name,'Not assigned')),
             b.Branch_Name) detail
           FROM appointment a LEFT JOIN staff s ON s.Staff_ID=a.Doctor_ID
           LEFT JOIN branch b ON b.Branch_ID=a.Branch_ID
           WHERE a.Patient_UHID=%s ORDER BY a.Appt_Date DESC,a.Time_Slot DESC LIMIT 100"""),
        ("Admission", """SELECT a.Admission_ID id,a.Admit_Date event_date,
             CONCAT('Inpatient admission · ',COALESCE(w.Ward_Name,'Ward')) label,
             IF(a.Discharge_Date IS NULL,'Active','Discharged') status,
             CONCAT_WS(' · ',w.Ward_Type,IF(a.Discharge_Date IS NULL,'Currently admitted',
             CONCAT('Discharged ',a.Discharge_Date))) detail
           FROM admission a LEFT JOIN ward w ON w.Ward_ID=a.Ward_ID
           WHERE a.Patient_UHID=%s ORDER BY a.Admit_Date DESC LIMIT 100"""),
        ("Prescription", """SELECT p.Prescription_ID id,p.Created_At event_date,
             CONCAT('Prescription · ',p.Medicine_Name) label,'Recorded' status,
             CONCAT('Dosage: ',p.Dosage,IF(p.Notes IS NULL OR p.Notes='','',
             CONCAT(' · ',p.Notes))) detail
           FROM prescription p JOIN appointment a ON a.Appt_ID=p.Appt_ID
           WHERE a.Patient_UHID=%s ORDER BY p.Created_At DESC LIMIT 100"""),
        ("Referral", """SELECT Referral_ID id,Created_At event_date,'Inter-branch referral' label,
             Status status,Reason detail FROM referral WHERE Patient_UHID=%s
           ORDER BY Created_At DESC LIMIT 100"""),
        ("Billing", """SELECT bi.Bill_ID id,bi.Generated_At event_date,'Hospital bill' label,
             bi.Status status,CONCAT('Total: ',bi.Total) detail
           FROM billing bi JOIN admission a ON a.Admission_ID=bi.Admission_ID
           WHERE a.Patient_UHID=%s ORDER BY bi.Generated_At DESC LIMIT 100"""),
    ]
    for kind, sql in queries:
        for row in fetch_all(sql, (uhid,)):
            records.append({
                "source": "AIIMS Connect", "resource_type": kind,
                "resource_id": str(row["id"]), "event_date": _iso(row.get("event_date")),
                "label": row.get("label") or kind, "status": row.get("status") or "Unknown",
                "detail": row.get("detail") or "",
            })
    return records


def _fhir_timeline(fhir_patient_id):
    """Read normalized FHIR projections, retaining resource-type distinctions."""
    records = []
    queries = [
        ("Encounter", """SELECT fhir_encounter_id id,
            COALESCE(NULLIF(type_display,''),NULLIF(class_display,''),'Clinical encounter') label,
            COALESCE(status,'Unknown') status,COALESCE(period_start,period_end) event_date,
            CONCAT_WS(' · ',NULLIF(class_display,''),NULLIF(class_code,'')) detail
            FROM fhir_encounter WHERE fhir_patient_id=%s
            ORDER BY COALESCE(period_start,period_end) DESC LIMIT 200"""),
        ("Observation", """SELECT fhir_observation_id id,
            COALESCE(NULLIF(code_display,''),NULLIF(code,''),'Clinical observation') label,
            COALESCE(status,'Unknown') status,effective_at event_date,
            CONCAT('Result: ',CASE WHEN value_numeric IS NOT NULL THEN
              CONCAT(CAST(value_numeric AS CHAR),IF(value_unit IS NULL OR value_unit='','',CONCAT(' ',value_unit)))
              WHEN value_text IS NOT NULL THEN value_text ELSE 'Not recorded' END,
              IF(code IS NULL,'',CONCAT(' · Code: ',code))) detail
            FROM fhir_observation WHERE fhir_patient_id=%s
            ORDER BY effective_at DESC LIMIT 300"""),
        ("Condition", """SELECT fhir_condition_id id,
            COALESCE(NULLIF(code_display,''),NULLIF(code,''),'Clinical condition') label,
            COALESCE(NULLIF(clinical_status_code,''),NULLIF(verification_status_code,''),'Recorded') status,
            COALESCE(onset_at,recorded_date) event_date,
            CONCAT('Code: ',COALESCE(code,'Not recorded'),
              IF(verification_status_code IS NULL,'',CONCAT(' · Verification: ',verification_status_code))) detail
            FROM fhir_condition WHERE fhir_patient_id=%s
            ORDER BY COALESCE(onset_at,recorded_date) DESC LIMIT 200"""),
        ("Procedure", """SELECT fhir_procedure_id id,
            COALESCE(NULLIF(code_display,''),NULLIF(code,''),'Clinical procedure') label,
            COALESCE(status,'Unknown') status,COALESCE(performed_start,performed_end) event_date,
            CONCAT('Code: ',COALESCE(code,'Not recorded')) detail
            FROM fhir_procedure WHERE fhir_patient_id=%s
            ORDER BY COALESCE(performed_start,performed_end) DESC LIMIT 200"""),
        ("MedicationRequest", """SELECT fhir_medication_request_id id,
            COALESCE(NULLIF(medication_display,''),'Medication request') label,
            COALESCE(status,'Unknown') status,authored_on event_date,
            CONCAT('Intent: ',COALESCE(intent,'Not recorded'),
              IF(dosage_text IS NULL OR dosage_text='','',CONCAT(' · ',dosage_text))) detail
            FROM fhir_medication_request WHERE fhir_patient_id=%s
            ORDER BY authored_on DESC LIMIT 200"""),
    ]
    for kind, sql in queries:
        for row in fetch_all(sql, (fhir_patient_id,)):
            records.append({
                "source": "FHIR R4", "resource_type": kind,
                "resource_id": str(row["id"]), "event_date": _iso(row.get("event_date")),
                "label": row.get("label") or kind, "status": row.get("status") or "Unknown",
                "detail": row.get("detail") or "",
            })
    return records


def _linked_fhir_patient(uhid):
    return fetch_one(
        """SELECT p.fhir_patient_id,p.full_name,p.gender,p.birth_date,p.phone,p.email,
                  l.link_note,l.updated_at
           FROM fhir_patient_link l JOIN fhir_patient p ON p.fhir_patient_id=l.fhir_patient_id
           WHERE l.UHID=%s AND l.link_status='linked'""",
        (uhid,),
    )


def _unlinked_fhir_candidates(query, limit=30):
    if len(query) < 2:
        return []
    return fetch_all(
        """SELECT p.fhir_patient_id,p.full_name,p.gender,p.birth_date
           FROM fhir_patient p LEFT JOIN fhir_patient_link l ON l.fhir_patient_id=p.fhir_patient_id
           WHERE (l.fhir_patient_id IS NULL OR (l.UHID IS NULL AND l.link_status='unlinked'))
             AND (p.full_name LIKE %s OR p.fhir_patient_id LIKE %s)
           ORDER BY p.full_name,p.fhir_patient_id LIMIT %s""",
        ("%" + query + "%", "%" + query + "%", limit),
    )


@bp.get("/patients/<uhid>/history")
def patient_history(uhid):
    denied = _guard_patient_access(uhid)
    if denied:
        return denied
    patient = fetch_one(
        "SELECT UHID,Name,DOB,Gender,Blood_Group,Phone,Address FROM patient WHERE UHID=%s",
        (uhid,),
    )
    if not patient:
        abort(404)
    query = request.args.get("q", "").strip()[:120]
    can_link = session.get("role") in LINK_ROLES
    fhir_ready = _clinical_schema_ready()
    linked = _linked_fhir_patient(uhid) if fhir_ready else None
    candidates = _unlinked_fhir_candidates(query) if fhir_ready and can_link and not linked else []
    timeline = _operational_timeline(uhid)
    fhir_records = _fhir_timeline(linked["fhir_patient_id"]) if fhir_ready and linked else []
    timeline.extend(fhir_records)
    timeline.sort(key=lambda item: item.get("event_date") or "", reverse=True)
    return render_template(
        "clinical_history.html", patient=patient, linked_fhir=linked,
        fhir_ready=fhir_ready, fhir_candidates=candidates, search_query=query,
        can_link=can_link and fhir_ready, timeline=timeline,
        operational_count=len(timeline) - len(fhir_records), fhir_count=len(fhir_records),
        fhir_url=url_for("fhir.explorer", patient=linked["fhir_patient_id"]) if linked else None,
    )


@bp.post("/patients/<uhid>/link")
def link_fhir_patient(uhid):
    denied = _guard_patient_access(uhid)
    if denied:
        return denied
    if session.get("role") not in LINK_ROLES:
        abort(403)
    if not _clinical_schema_ready():
        flash("FHIR clinical tables are not installed yet. Apply the relational FHIR migration first.", "warning")
        return redirect(url_for("clinical.patient_history", uhid=uhid))
    patient = fetch_one("SELECT UHID FROM patient WHERE UHID=%s", (uhid,))
    fhir_id = request.form.get("fhir_patient_id", "").strip()[:64]
    fhir_patient = fetch_one("SELECT fhir_patient_id FROM fhir_patient WHERE fhir_patient_id=%s", (fhir_id,))
    if not patient or not fhir_patient:
        flash("Choose an existing operational UHID and an imported FHIR Patient.", "danger")
        return redirect(url_for("clinical.patient_history", uhid=uhid))
    note = request.form.get("link_note", "").strip()[:180]
    audit_note = (note + " · " if note else "") + "Linked by staff login " + str(session.get("login_id") or "staff")
    connection = connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT fhir_patient_id,UHID,link_status FROM fhir_patient_link
               WHERE fhir_patient_id=%s OR UHID=%s FOR UPDATE""", (fhir_id, uhid)
        )
        existing = cursor.fetchall()
        same_fhir = next((row for row in existing if row["fhir_patient_id"] == fhir_id), None)
        other_uhid = next((row for row in existing if row.get("UHID") == uhid and row["fhir_patient_id"] != fhir_id), None)
        if other_uhid:
            raise ValueError("This UHID is already linked to another FHIR identity. Unlink it before making a different verified match.")
        if same_fhir and same_fhir.get("UHID") == uhid and same_fhir.get("link_status") == "linked":
            connection.commit()
            flash("This FHIR Patient is already linked to this UHID.", "info")
            return redirect(url_for("clinical.patient_history", uhid=uhid))
        if same_fhir and (same_fhir.get("UHID") is not None or same_fhir.get("link_status") != "unlinked"):
            raise ValueError("This FHIR Patient is already linked to another UHID. Unlink it before changing the mapping.")
        if same_fhir:
            cursor.execute(
                """UPDATE fhir_patient_link SET UHID=%s,link_status='linked',link_note=%s
                   WHERE fhir_patient_id=%s AND UHID IS NULL AND link_status='unlinked'""",
                (uhid, audit_note, fhir_id),
            )
        else:
            cursor.execute(
                """INSERT INTO fhir_patient_link (fhir_patient_id,UHID,link_status,link_note)
                   VALUES (%s,%s,'linked',%s)""", (fhir_id, uhid, audit_note)
            )
        connection.commit()
        flash("FHIR clinical history linked to UHID " + uhid + ".", "success")
    except ValueError as exc:
        connection.rollback()
        flash(str(exc), "warning")
    except mysql.connector.Error as exc:
        connection.rollback()
        log.exception("FHIR patient link failed")
        if getattr(exc, "errno", None) == 1062:
            flash("That FHIR Patient or UHID is already linked. Refresh the page and review the current mapping.", "warning")
        else:
            flash("The FHIR identity could not be linked. The operational patient record was not changed.", "danger")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("clinical.patient_history", uhid=uhid))


@bp.post("/patients/<uhid>/unlink")
def unlink_fhir_patient(uhid):
    denied = _guard_patient_access(uhid)
    if denied:
        return denied
    if session.get("role") not in LINK_ROLES:
        abort(403)
    if not _clinical_schema_ready():
        flash("FHIR clinical tables are not installed yet.", "warning")
        return redirect(url_for("clinical.patient_history", uhid=uhid))
    fhir_id = request.form.get("fhir_patient_id", "").strip()[:64]
    note = request.form.get("link_note", "").strip()[:180]
    audit_note = (note + " · " if note else "") + "Unlinked by staff login " + str(session.get("login_id") or "staff")
    try:
        _, count = execute(
            """UPDATE fhir_patient_link SET UHID=NULL,link_status='unlinked',link_note=%s
               WHERE fhir_patient_id=%s AND UHID=%s AND link_status='linked'""",
            (audit_note, fhir_id, uhid), actor_login_id=session.get("login_id"),
        )
        flash(
            "FHIR identity unlinked. The original FHIR records remain safely stored."
            if count else "No matching active FHIR link was found.",
            "success" if count else "warning",
        )
    except mysql.connector.Error:
        log.exception("FHIR patient unlink failed")
        flash("The FHIR identity could not be unlinked.", "danger")
    return redirect(url_for("clinical.patient_history", uhid=uhid))
