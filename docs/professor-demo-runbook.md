# AIIMS Connect — professor demonstration runbook

Use synthetic demonstration accounts and records only. This is an academic prototype, not a clinical information system.

## Before the demo
1. Confirm /healthz returns a healthy database status.
2. Open the web app in one browser and MySQL Workbench in another.
3. Connect Workbench to the same database used by Flask. For Railway, use the Railway MySQL TCP Proxy. For a local demo, use localhost.
4. In Workbench, select aiims_connect and keep these queries ready:

    SELECT COUNT(*) AS patients FROM patient;
    SELECT COUNT(*) AS appointments FROM appointment;
    SELECT COUNT(*) AS admissions FROM admission;
    SELECT COUNT(*) AS referrals FROM referral;

## Suggested live workflow
1. Sign in using an existing administrator or receptionist account.
2. Register a new synthetic patient and note the generated UHID.
3. In Workbench, query patient by the new UHID to show the row persisted.
4. Book an OPD appointment with a doctor at the correct branch. Show the appointment ID and token.
5. In Workbench, inspect appointment and doctor_schedule_view.
6. Sign in as the doctor, complete the appointment and add a synthetic prescription.
7. Show the prescription and linked patient_history_view record in Workbench.
8. Admit a synthetic patient to an available ward. Query ward and branch_ward_view to show Available_Beds changed.
9. Discharge the admission with demo charges. Show the bill and restored ward capacity.
10. Create a referral to another branch as a doctor, then accept it as the receiving branch administrator/receptionist.
11. Mark a synthetic bill paid and show the payment status and revenue report.

## DBMS concepts to explain
- Primary keys, foreign keys and chain-wide UHID.
- Branch-aware records and the doctor/branch consistency trigger.
- Unique generated keys preventing duplicate active OPD slots/tokens.
- Stored procedures for registration, appointment, admission, discharge, billing and referral transitions.
- Triggers for ward capacity and audit logging through @app_login_id.
- Views for patient history, schedules, branch occupancy, ward capacity and revenue.

## Safety
- Never import the Railway structure bootstrap into the populated local database.
- The data seeder defaults to preview. Apply it only to a DB containing synthetic demo/test records.
- Do not use real patient names, phone numbers, UHIDs, clinical histories or credentials.
- Do not expose the MySQL root account publicly.
