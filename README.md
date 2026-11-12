# AIIMS Connect

**One Patient. One ID. Every Branch.**

AIIMS Connect is an independent academic multi-branch hospital-operations prototype built with Flask, MySQL, Bootstrap and Chart.js. It demonstrates a shared UHID, outpatient appointments, admissions, prescriptions, inter-branch referrals, billing and reporting.

> Not affiliated with AIIMS or the Government of India. Not validated or secured for real clinical use. Use synthetic demonstration data only.

## Database compatibility

This application is adapted to the structure-only export you provided from MySQL 8.0.46. It expects:

- 15 tables: admin_staff, admission, appointment, audit_log, billing, branch, department, doctor, login, patient, prescription, receptionist, referral, staff and ward.
- 7 views: branch_revenue_view, branch_ward_view, chain_occupancy_view, doctor_schedule_view, patient_history_view, patient_self_view and referral_flow_view.
- 11 stored procedures and 14 triggers.

The Flask workflows call your existing procedures for patient registration, appointment booking/cancellation/completion, admission, discharge and bill generation, prescriptions, referral acceptance/rejection and bill payment. Login roles are mapped from Admin, Doctor, Receptionist and Patient; admin_staff.Access_Level distinguishes Chain and Branch administrators.

Do not run old generic schema, seed or admin-setup SQL files from earlier versions. They were written for a different schema. The web application does not recreate or migrate your existing local database.

## Local Windows setup — preserve the current database

1. Confirm the MySQL Server service is running and Workbench connects successfully.

2. Pull the latest code:

```powershell
git clone https://github.com/bitmorphic/aiims-connect.git
cd aiims-connect
# If you already cloned it, run: git pull origin main
```

3. Use Python 3.12 (64-bit), then install the dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Or double-click setup.bat.

4. Create your private environment file:

```powershell
Copy-Item .env.example .env
py -3.12 -c "import secrets; print(secrets.token_hex(32))"
notepad .env
```

Set DB_HOST=127.0.0.1, DB_PORT=3306, DB_NAME=aiims_connect and enter the username/password that successfully connect in your local Workbench connection. The template uses root because your Workbench screenshot showed root@localhost; keep root local-only and never use it for the public Railway app. Put the generated random value in FLASK_SECRET_KEY. Never commit .env.

5. Verify the existing database. This is read-only:

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

It checks for the expected tables, views, procedures and triggers. It does not create, drop, seed or alter database objects.

6. Preview the optional synthetic-data top-up. The default is read-only:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

Only after confirming the connected database contains synthetic demo/test records, apply the top-up:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --apply
```

Targets are modest ceilings: 40 patients, 55 appointments, 30 prescriptions, 18 admissions, 12 bills and 10 referrals. It only adds missing synthetic records and never updates/deletes existing rows or resets existing passwords. New patient accounts use password Demo@12345 and usernames demo.patient.01, demo.patient.02, etc. Do not apply this to a database containing real patient information.

7. Start Flask:

```powershell
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000 and keep PowerShell running. The root URL is the redesigned public landing page; choose Open workspace to sign in.

## Existing login accounts

The app authenticates against the records already in your login table. It does not reset their passwords. Use your existing usernames/passwords.

- Admin with Access_Level=Chain: Chain administrator.
- Admin with Access_Level=Branch: Branch administrator.
- Doctor: Doctor workspace.
- Receptionist: Receptionist workspace.
- Patient: Patient portal.

If the seeder is run on a completely empty database, it creates a small synthetic starter network with these staff usernames: chain.admin; admin.new.delhi, admin.jodhpur and admin.bhopal; doctor.new.delhi.01, doctor.jodhpur.01 and doctor.bhopal.01; receptionist.new.delhi.01, receptionist.jodhpur.01 and receptionist.bhopal.01. Their initial password is Demo@12345. On an already-populated database, existing staff credentials remain unchanged.

## Railway + MySQL Workbench

The public Railway Flask app and Workbench can connect to the same Railway MySQL database. Your laptop's local MySQL remains separate and untouched.

1. Create a Railway MySQL service and deploy this repository as a Flask web service.

2. In the Flask service Variables, map the Railway MySQL private variables to the app's names. Replace MySQL with your exact Railway service name:

```text
DB_HOST=${{MySQL.MYSQLHOST}}
DB_PORT=${{MySQL.MYSQLPORT}}
DB_USER=${{MySQL.MYSQLUSER}}
DB_PASSWORD=${{MySQL.MYSQLPASSWORD}}
DB_NAME=${{MySQL.MYSQLDATABASE}}
FLASK_SECRET_KEY=<a fresh random secret>
FLASK_DEBUG=0
COOKIE_SECURE=1
```

3. Copy your structure-only export (aiims_connect_structure.sql) into the repository folder on your laptop. Generate a safe bootstrap:

```powershell
py -3.12 scripts\prepare_railway_schema.py aiims_connect_structure.sql aiims_connect_railway_schema.sql
```

4. In Workbench, connect to Railway using the MySQL service TCP Proxy host and port, plus the Railway MySQL username/password. Select the new, empty Railway schema and execute aiims_connect_railway_schema.sql. This generated file contains CREATE statements only: no patient rows, login credentials, appointments, transaction rows or DROP statements. It removes the local DEFINER account so the account importing the file becomes the definer. Import it only into a new empty target schema, never into your populated local database.

5. Point a temporary local .env at the Railway private connection (or use another approved secure tunnel) and run scripts\init_db.py to verify the new Railway database. Do not place database secrets in the repository.

6. Deploy the Flask service. Procfile starts Gunicorn on Railway's assigned $PORT. /healthz checks database connectivity.

7. To watch live writes, keep Flask configured with Railway's private MySQL connection and Workbench connected through Railway's TCP Proxy. Both then see the same Railway rows. A Flask process configured with 127.0.0.1 writes only to local MySQL.

The structure export does not migrate your local rows to Railway. Do not migrate real patient information; use synthetic data only.

## Modules

- Public landing page and sign-in.
- Role-aware dashboard with branch occupancy and recent appointments.
- Central patient registry and patient care-history view.
- OPD appointments: booking, cancellation and completion.
- Ward/bed availability and IPD admissions.
- Discharge with automatic bill generation.
- Doctor prescriptions and inter-branch referrals.
- Billing, payment status and branch revenue/occupancy reports.

## Demo guide and tests

See docs/professor-demo-runbook.md for the recommended end-to-end walkthrough and Workbench queries.

Run the repository smoke tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Smoke tests are not a substitute for integration testing against your actual MySQL instance. The deployed Railway database and every role/workflow must still be exercised before the professor demo.