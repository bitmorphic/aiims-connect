"""Read-only verification of the existing AIIMS Connect schema."""
from app.db import connect

EXPECTED = {
    "tables": {"admin_staff","admission","appointment","audit_log","billing","branch",
               "department","doctor","login","patient","prescription","receptionist",
               "referral","staff","ward"},
    "views": {"branch_revenue_view","branch_ward_view","chain_occupancy_view",
              "doctor_schedule_view","patient_history_view","patient_self_view",
              "referral_flow_view"},
    "procedures": {"AcceptReferral","AdmitPatient","BookAppointment","CancelAppointment",
                   "CompleteAppointment","CreatePrescription","DischargePatient",
                   "GenerateBill","MarkBillPaid","RegisterPatient","RejectReferral"},
    "triggers": {"trg_admission_capacity_bi","trg_admission_discharge_bu",
                 "trg_appt_doctor_branch_bi","trg_appt_doctor_branch_bu",
                 "trg_bill_audit_ai","trg_bill_audit_au",
                 "trg_login_role_consistency_bi","trg_login_role_consistency_bu",
                 "trg_rx_audit_ai","trg_rx_audit_au","trg_ref_initiator_branch_bi",
                 "trg_ref_audit_ai","trg_ref_initiator_branch_bu","trg_ref_audit_au"},
}


def main():
    cn = connect()
    cur = cn.cursor()
    try:
        cur.execute("SELECT DATABASE(),VERSION()")
        db, version = cur.fetchone()
        cur.execute("SELECT TABLE_NAME,TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()")
        objects = cur.fetchall()
        actual = {
            "tables": {n for n,t in objects if t == "BASE TABLE"},
            "views": {n for n,t in objects if t == "VIEW"},
        }
        cur.execute("SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_TYPE='PROCEDURE'")
        actual["procedures"] = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE()")
        actual["triggers"] = {r[0] for r in cur.fetchall()}
        print("Database:", db, "| MySQL:", version)
        failed = False
        for kind, expected in EXPECTED.items():
            missing = sorted(expected - actual[kind])
            print(kind, len(actual[kind]), "found;", len(expected), "expected")
            if missing:
                failed = True
                print("Missing:", ", ".join(missing))
        if failed:
            print("Verification failed. No database object was changed.")
            return 1
        print("Schema verification passed. Read-only check complete.")
        return 0
    finally:
        cur.close()
        cn.close()


if __name__ == "__main__":
    raise SystemExit(main())
