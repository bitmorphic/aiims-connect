#!/usr/bin/env python3
"""Preview or remove records created by the legacy AIIMS Connect demo seeder.

This cleanup is deliberately narrow:
- patient accounts must use the exact legacy demo.patient.* username prefix;
- synthetic staff must have a Staff.Name beginning with "Demo " and a
  linked login account;
- clinical rows are removed only when linked to those patients or doctors.

Branch, department and ward configuration is preserved. FHIR resources and
FHIR import batches are never modified. Default mode is read-only.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from app.db import connect


CONFIRMATION = "REMOVE ONLY LEGACY AIIMS CONNECT DEMO DATA"


def _marks(values):
    return ",".join(["%s"] * len(values))


def _fetch(cursor, sql, params=()):
    cursor.execute(sql, tuple(params))
    return cursor.fetchall()


def _ids(rows, field):
    return [row[field] for row in rows if row.get(field) is not None]


def build_cleanup_plan(cursor):
    """Return exact legacy-demo row identifiers and counts without writing."""
    patient_logins = _fetch(
        cursor,
        "SELECT l.Login_ID, l.Username, l.Patient_UHID, p.Name AS Patient_Name "
        "FROM login l LEFT JOIN patient p ON p.UHID=l.Patient_UHID "
        "WHERE l.Role='Patient' AND l.Username LIKE 'demo.patient.%' "
        "ORDER BY l.Login_ID",
    )
    patient_login_ids = _ids(patient_logins, "Login_ID")
    patient_uhids = sorted(set(_ids(patient_logins, "Patient_UHID")))

    demo_staff = _fetch(
        cursor,
        "SELECT s.Staff_ID, s.Staff_Type, s.Name AS Staff_Name, l.Login_ID, l.Username "
        "FROM staff s JOIN login l ON l.Staff_ID=s.Staff_ID "
        "WHERE s.Name LIKE 'Demo %' "
        "ORDER BY s.Staff_ID",
    )
    active_non_demo_admins = _fetch(
        cursor,
        "SELECT l.Login_ID, l.Username, s.Name AS Staff_Name "
        "FROM login l JOIN staff s ON s.Staff_ID=l.Staff_ID "
        "JOIN admin_staff a ON a.Staff_ID=s.Staff_ID "
        "WHERE l.Is_Active=1 AND l.Role='Admin' "
        "AND a.Access_Level IN ('Chain','Branch') "
        "AND s.Name NOT LIKE 'Demo %' AND l.Username NOT LIKE 'demo.%' "
        "ORDER BY l.Login_ID",
    )
    # Never remove the only working admin access path. If the legacy demo
    # accounts are the only administrators, retain all demo staff and any
    # appointments/referrals belonging to those doctors until a real admin
    # account has been provisioned.
    staff_cleanup_blocked = not bool(active_non_demo_admins)
    staff_to_remove = [] if staff_cleanup_blocked else demo_staff
    staff_ids = sorted(set(_ids(staff_to_remove, "Staff_ID")))
    staff_login_ids = sorted(set(_ids(staff_to_remove, "Login_ID")))
    doctor_ids = sorted({
        row["Staff_ID"] for row in staff_to_remove if row.get("Staff_Type") == "Doctor"
    })

    referral_clauses = []
    referral_params = []
    if patient_uhids:
        referral_clauses.append("Patient_UHID IN (" + _marks(patient_uhids) + ")")
        referral_params.extend(patient_uhids)
    if doctor_ids:
        referral_clauses.append("Initiator_Staff_ID IN (" + _marks(doctor_ids) + ")")
        referral_params.extend(doctor_ids)
    referrals = []
    if referral_clauses:
        referrals = _fetch(
            cursor,
            "SELECT Referral_ID FROM referral WHERE " + " OR ".join(referral_clauses),
            referral_params,
        )
    referral_ids = _ids(referrals, "Referral_ID")

    appt_clauses = []
    appt_params = []
    if patient_uhids:
        appt_clauses.append("Patient_UHID IN (" + _marks(patient_uhids) + ")")
        appt_params.extend(patient_uhids)
    if doctor_ids:
        appt_clauses.append("Doctor_ID IN (" + _marks(doctor_ids) + ")")
        appt_params.extend(doctor_ids)
    if referral_ids:
        appt_clauses.append("Referral_ID IN (" + _marks(referral_ids) + ")")
        appt_params.extend(referral_ids)
    appointments = []
    if appt_clauses:
        appointments = _fetch(
            cursor,
            "SELECT Appt_ID FROM appointment WHERE " + " OR ".join(appt_clauses),
            appt_params,
        )
    appointment_ids = _ids(appointments, "Appt_ID")

    admissions = []
    if patient_uhids:
        admissions = _fetch(
            cursor,
            "SELECT Admission_ID FROM admission WHERE Patient_UHID IN ("
            + _marks(patient_uhids) + ")",
            patient_uhids,
        )
    admission_ids = _ids(admissions, "Admission_ID")

    bills = []
    if admission_ids:
        bills = _fetch(
            cursor,
            "SELECT Bill_ID FROM billing WHERE Admission_ID IN ("
            + _marks(admission_ids) + ")",
            admission_ids,
        )
    prescriptions = []
    if appointment_ids:
        prescriptions = _fetch(
            cursor,
            "SELECT Prescription_ID FROM prescription WHERE Appt_ID IN ("
            + _marks(appointment_ids) + ")",
            appointment_ids,
        )

    all_login_ids = sorted(set(patient_login_ids + staff_login_ids))
    fhir_tables = _fetch(
        cursor,
        "SELECT COUNT(*) AS table_count FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='fhir_resource'",
    )
    fhir_resource_count = None
    if fhir_tables and fhir_tables[0]["table_count"]:
        fhir_row = _fetch(cursor, "SELECT COUNT(*) AS row_count FROM fhir_resource")
        fhir_resource_count = int(fhir_row[0]["row_count"])

    counts = OrderedDict([
        ("legacy demo patient accounts", len(patient_login_ids)),
        ("legacy demo patient records", len(patient_uhids)),
        ("appointments linked to demo patients/doctors", len(appointment_ids)),
        ("prescriptions linked to those appointments", len(_ids(prescriptions, "Prescription_ID"))),
        ("admissions for demo patients", len(admission_ids)),
        ("bills for those admissions", len(_ids(bills, "Bill_ID"))),
        ("referrals linked to demo patients/doctors", len(referral_ids)),
        ("legacy Demo staff records eligible for removal", len(staff_ids)),
        ("legacy Demo staff logins eligible for removal", len(staff_login_ids)),
        ("active non-demo administrator accounts preserved", len(active_non_demo_admins)),
    ])
    return {
        "patient_logins": patient_logins,
        "demo_staff": demo_staff,
        "active_non_demo_admins": active_non_demo_admins,
        "staff_cleanup_blocked": staff_cleanup_blocked,
        "patient_login_ids": patient_login_ids,
        "patient_uhids": patient_uhids,
        "staff_ids": staff_ids,
        "staff_login_ids": staff_login_ids,
        "doctor_ids": doctor_ids,
        "referral_ids": referral_ids,
        "appointment_ids": appointment_ids,
        "admission_ids": admission_ids,
        "counts": counts,
        "fhir_resource_count": fhir_resource_count,
    }


def _delete_ids(cursor, table, column, values):
    if not values:
        return 0
    cursor.execute(
        "DELETE FROM " + table + " WHERE " + column + " IN (" + _marks(values) + ")",
        tuple(values),
    )
    return cursor.rowcount


def apply_cleanup(cursor, plan):
    """Delete only planned demo-linked rows; caller owns the transaction."""
    deleted = {}
    deleted["prescription"] = _delete_ids(cursor, "prescription", "Appt_ID", plan["appointment_ids"])
    deleted["billing"] = _delete_ids(cursor, "billing", "Admission_ID", plan["admission_ids"])
    deleted["admission"] = _delete_ids(cursor, "admission", "Admission_ID", plan["admission_ids"])
    deleted["appointment"] = _delete_ids(cursor, "appointment", "Appt_ID", plan["appointment_ids"])
    deleted["referral"] = _delete_ids(cursor, "referral", "Referral_ID", plan["referral_ids"])

    # Preserve audit events but anonymize references to demo accounts before
    # removing those login rows; Actor_Login_ID is nullable by design.
    demo_login_ids = sorted(set(plan["patient_login_ids"] + plan["staff_login_ids"]))
    if demo_login_ids:
        cursor.execute(
            "UPDATE audit_log SET Actor_Login_ID=NULL WHERE Actor_Login_ID IN ("
            + _marks(demo_login_ids) + ")",
            tuple(demo_login_ids),
        )

    deleted["patient_login"] = _delete_ids(cursor, "login", "Login_ID", plan["patient_login_ids"])
    deleted["staff_login"] = _delete_ids(cursor, "login", "Login_ID", plan["staff_login_ids"])
    deleted["patient"] = _delete_ids(cursor, "patient", "UHID", plan["patient_uhids"])

    # Remove subtype rows before their STAFF parent. Only seeder-created staff
    # (Name LIKE 'Demo %' with a linked login) are included in this plan.
    for table in ("doctor", "admin_staff", "receptionist"):
        deleted[table] = _delete_ids(cursor, table, "Staff_ID", plan["staff_ids"])
    deleted["staff"] = _delete_ids(cursor, "staff", "Staff_ID", plan["staff_ids"])
    return deleted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="execute the cleanup (default is preview only)")
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="confirm that a restorable database backup exists",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help='must exactly equal: "' + CONFIRMATION + '"',
    )
    args = parser.parse_args()

    if args.apply and not args.backup_confirmed:
        parser.error("--apply requires --backup-confirmed after taking a restorable database backup")
    if args.apply and args.confirm != CONFIRMATION:
        parser.error('--apply requires --confirm "' + CONFIRMATION + '"')

    connection = connect()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT DATABASE() AS db_name, VERSION() AS mysql_version")
        target = cursor.fetchone()
        if not target or not target.get("db_name"):
            raise RuntimeError("No database is selected. Refusing to continue.")
        print("Database:", target["db_name"], "| MySQL:", target["mysql_version"])

        plan = build_cleanup_plan(cursor)
        print("\nLegacy demo cleanup preview:")
        for label, count in plan["counts"].items():
            print(f"  {label:54} {count:>8,}")

        if plan["patient_logins"]:
            print("\nPatient accounts selected:")
            for row in plan["patient_logins"]:
                print(f"  {row['Username']} -> {row.get('Patient_UHID') or '(no UHID)'} | {row.get('Patient_Name') or '(name unavailable)'}")
        if plan["demo_staff"]:
            print("\nStaff accounts selected:")
            for row in plan["demo_staff"]:
                print(f"  {row['Username']} -> {row['Staff_Name']} | {row['Staff_Type']} #{row['Staff_ID']}")
        if plan["fhir_resource_count"] is None:
            print("\nFHIR store: table is not installed yet; no FHIR rows will be touched.")
        else:
            print(f"\nFHIR resources preserved: {plan['fhir_resource_count']:,}")
        print("Preserved: branches, departments, wards, non-demo staff/accounts, and audit events.")

        if not args.apply:
            print("\nPREVIEW ONLY. No rows were changed.")
            print("After reviewing the counts and taking a backup, run with --apply,")
            print("--backup-confirmed, and the exact --confirm phrase shown in --help.")
            return 0

        # End the read-only preview transaction before starting the write transaction.
        connection.commit()
        connection.start_transaction()
        deleted = apply_cleanup(cursor, plan)
        if plan["fhir_resource_count"] is not None:
            cursor.execute("SELECT COUNT(*) AS row_count FROM fhir_resource")
            after = int(cursor.fetchone()["row_count"])
            if after != plan["fhir_resource_count"]:
                raise RuntimeError("FHIR resource count changed unexpectedly; rolling back cleanup.")
        else:
            after = None
        connection.commit()
        print("\nCleanup committed:")
        for table, count in deleted.items():
            print(f"  {table:20} {count:>8,}")
        if after is not None:
            print(f"  FHIR resources preserved: {after:,}")
        print("\nDone. Operational demo patients and their linked demo activity were removed.")
        print("FHIR resources remain isolated and available through the staff-only FHIR API.")
        return 0
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
