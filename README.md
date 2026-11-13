<div align="center">
  <h1>AIIMS Connect</h1>
  <p><strong>One Patient. One ID. Every Branch.</strong></p>
  <p>An academic multi-branch hospital management system built around a chain-wide patient identity and branch-specific care records.</p>
</div>

> **Academic prototype notice:** AIIMS Connect is an independent student project inspired by the multi-branch hospital use case. It is **not affiliated with, endorsed by, or an official system of AIIMS or the Government of India**. It is not certified or validated for clinical use. Use synthetic demonstration data only; never enter real patient information.

## Project overview

AIIMS Connect models a hospital network in which a patient registers once and receives a unique Health Identifier (UHID) that remains valid across branches. Appointments, admissions, prescriptions, referrals and bills are recorded against the relevant branch, while authorised management roles can view network-level information.

The central database is MySQL. A Flask web application provides role-aware pages for patient services, OPD scheduling, inpatient admissions, ward capacity, inter-branch referrals, prescriptions, billing and reporting.

### The problem this project addresses

A patient may visit more than one campus over time. The system therefore needs to preserve one patient identity across the network without losing the branch context of each care event. It must also prevent conflicting actions such as booking the same doctor's active time slot twice or assigning more patients than a ward can accommodate. Multi-step actions such as admission, discharge and referral acceptance need consistent database updates.

### Project objectives

- Maintain one chain-wide patient registry and a unique UHID per patient.
- Keep appointments, admissions, prescriptions, referrals and bills associated with their relevant branch.
- Provide role-appropriate access for network administrators, branch administrators, doctors, receptionists and patients.
- Coordinate OPD booking, bed capacity and inter-branch referrals through database-backed workflows.
- Use relational constraints, transactions, views, stored procedures and triggers to keep records consistent.
- Provide branch-level and network-level summaries for occupancy and operational activity.

## Main modules

| Module | What it does |
| --- | --- |
| Authentication and workspace | Sign-in against the hospital database and role-aware workspace navigation. |
| Patient registry | Register a patient once, generate a UHID, and search/view patient records. |
| Branch and department context | Keep staff, wards, doctors and care records connected to their branch. |
| OPD appointments | Book and manage appointments with doctor, branch, date, time-slot and token rules. |
| Admissions and wards | Admit patients to wards, maintain available-bed counts and record discharge. |
| Referrals | Refer a patient from one branch to another and track the referral through acceptance or rejection. Acceptance creates an appointment at the receiving branch. |
| Prescriptions | Record medicine, dosage and notes against an appointment. |
| Billing and payments | Generate a bill at discharge, calculate charges and update payment status. |
| Reports | Display branch occupancy, revenue and network-level summaries from database views. |
| Audit records | Maintain records of selected sensitive database actions. |

The original synopsis describes a wider operational model, including a dedicated nurse role and blood-bank inventory. Those are part of the case-study scope, but are **not presented here as completed workflows in the current web application**.

## Database design

The current schema is organised around 15 entities:

`BRANCH`, `DEPARTMENT`, `WARD`, `LOGIN`, `STAFF`, `DOCTOR`, `RECEPTIONIST`, `ADMIN_STAFF`, `PATIENT`, `APPOINTMENT`, `PRESCRIPTION`, `ADMISSION`, `BILLING`, `REFERRAL` and `AUDIT_LOG`.

Key design decisions:

- **Chain-wide identity:** `PATIENT.UHID` identifies a patient across branches.
- **Branch-aware activity:** appointments, admissions and referrals retain branch context; billing is tied to an admission.
- **Staff specialisation:** `STAFF` is specialised into doctor, receptionist and admin-staff records.
- **Ward capacity:** `WARD.Available_Beds` is maintained by database triggers when admissions are created or discharged.
- **Referral flow:** a referral stores source and destination branches; accepting it creates an appointment for the receiving branch.
- **Derived values:** generated/trigger-maintained values reduce the chance of inconsistent manually maintained totals or counts.

### Entity-relationship diagram

The ER diagram below represents the current 15-entity schema.

![AIIMS Connect entity relationship diagram](aiims_connect_er_diagram.png)

### DBMS objects

| Database object | Count | Purpose |
| --- | ---: | --- |
| Tables | 15 | Core patient, staff, branch, appointment, admission, billing and referral records. |
| Views | 7 | Role-oriented data and aggregated patient-history, ward, occupancy, referral and revenue information. |
| Stored procedures | 11 | Encapsulate database workflows such as booking, admission, discharge, billing and referral transitions. |
| Triggers | 14 | Enforce or maintain selected data rules, including bed-capacity updates and audit entries. |

The seven views in the current schema are `branch_revenue_view`, `branch_ward_view`, `chain_occupancy_view`, `doctor_schedule_view`, `patient_history_view`, `patient_self_view` and `referral_flow_view`.

### DBMS concepts demonstrated

| Concept | How it is used in the project |
| --- | --- |
| Relational modelling | Primary keys, foreign keys and branch-aware relationships connect the network data. |
| EER specialisation | Staff subtypes and the patient-care model are represented in the design. |
| Normalisation | The schema separates patient, staff, login, branch and care-event data to reduce duplication. |
| Transactions | Multi-step operations are grouped so related changes can commit or roll back together. |
| Concurrency control | Database locking and uniqueness rules protect shared resources such as doctor time slots and ward capacity. |
| Constraints and indexes | Key, check and uniqueness rules protect records and support common searches. |
| Views | Provide reusable patient, schedule, ward, occupancy, referral and revenue summaries. |
| Stored procedures and triggers | Keep important workflow and record-maintenance logic close to the data. |
| Security | Password hashing, role-aware access and audit records are included in the application/database design. |
| SQL operations | The project uses DDL, DML, DCL and TCL, including joins, subqueries, aggregate queries, `COMMIT` and `ROLLBACK`. |

More details are available in [`docs/database-design.md`](docs/database-design.md), [`docs/dbms-demonstrations.md`](docs/dbms-demonstrations.md) and [`docs/viva-questions.md`](docs/viva-questions.md).

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, Flask 3.x, Jinja templates |
| Database | MySQL Community Server 8.4 |
| Database connector | `mysql-connector-python` 9.x |
| Frontend | HTML5, CSS3 and JavaScript |
| Password hashing | `bcrypt` |
| Configuration | `python-dotenv` |
| Production server | Gunicorn |
| Database administration | MySQL Workbench |
| Version control | Git and GitHub |
| Hosting | Railway |

## User roles

| Role | Scope |
| --- | --- |
| Chain administrator | Network-wide overview and consolidated branch reporting. |
| Branch administrator | Administrative operations and records for the assigned branch. |
| Doctor | Assigned OPD schedule, prescriptions and inter-branch referrals. |
| Receptionist | Patient registration, appointment coordination and related branch workflows. |
| Patient | Own profile and available care-history, prescription, admission and billing information. |

The synopsis also identifies nursing staff as an operational stakeholder. The current sign-in implementation documents the roles above; it does not claim a separate nurse workspace.

## Repository structure

```text
aiims-connect/
├── app/
│   ├── __init__.py
│   ├── db.py
│   └── routes.py
├── docs/
│   ├── api.md
│   ├── database-design.md
│   ├── dbms-demonstrations.md
│   ├── professor-demo-runbook.md
│   ├── test-plan.md
│   └── viva-questions.md
├── scripts/
│   ├── init_db.py
│   ├── prepare_railway_schema.py
│   └── seed_demo.py
├── sql/
├── static/
│   ├── app.js
│   └── style.css
├── templates/
├── tests/
├── .env.example
├── Procfile
├── requirements.txt
├── runtime.txt
├── run.py
└── setup.bat
```

## Run locally (Windows)

### Prerequisites

- Python 3.12 (64-bit)
- MySQL Server 8.4 and MySQL Workbench
- Git

### 1. Clone the repository

```powershell
git clone https://github.com/bitmorphic/aiims-connect.git
cd aiims-connect
```

For an existing clone, use `git pull origin main`.

### 2. Create the environment and install dependencies

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Or run `setup.bat`.

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
py -3.12 -c "import secrets; print(secrets.token_hex(32))"
notepad .env
```

Set the database host, port, database name and credentials for your local MySQL instance, and place the generated random value in `FLASK_SECRET_KEY`. Keep `.env` private and never commit it. Use a least-privilege MySQL account for application access; do not expose a local root account to the public web.

### 4. Verify the existing database

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

This is a read-only schema check. It expects the existing AIIMS Connect schema, including the tables, views, procedures and triggers described above. It does not create, drop, seed or migrate database objects.

### 5. Optional: preview synthetic demo data

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

The default is preview-only. Review the proposed changes before applying them. To apply the synthetic top-up:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --apply
```

Run the seeder only against a database containing synthetic demonstration/test records. It is not a migration utility and must never be applied to real patient data.

### 6. Start the application

```powershell
.\.venv\Scripts\python.exe run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the terminal running while using the application. Sign in with an account provisioned in the database.

## Railway deployment

The project is deployed as a Flask web service on Railway and uses a Railway MySQL service. The public demo address is:

**[Open the AIIMS Connect demo](https://web-production-d89a88e6.up.railway.app/)**

For a fresh Railway environment, configure the web service to use Railway's private MySQL variables (replace `MySQL` with the actual database service name):

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

To bootstrap a **new, empty** Railway database:

1. Start with a structure-only export from the intended MySQL schema.
2. Generate a Railway-safe schema file:

   ```powershell
   py -3.12 scripts\prepare_railway_schema.py aiims_connect_structure.sql aiims_connect_railway_schema.sql
   ```

3. Import the generated CREATE-only bootstrap into the new, empty Railway schema using MySQL Workbench and the Railway MySQL TCP Proxy.
4. Verify the schema using `scripts/init_db.py`, then deploy the Flask service.

The structure bootstrap does not migrate local rows. Do not import it into a populated database. The public web service should use Railway's private network connection; Workbench can use the database TCP Proxy. See [`sql/README.md`](sql/README.md) for the database deployment notes.

## Demonstration workflow

A typical end-to-end demonstration follows this sequence:

1. Register a synthetic patient and note the generated UHID.
2. Book an OPD appointment at a selected branch and verify the assigned token.
3. Complete the appointment as the doctor and create a prescription.
4. Admit the patient to an available ward and observe the available-bed count update.
5. Discharge the patient, generate the bill, and update its payment status.
6. Create a referral to another branch, accept it at the destination, and verify the appointment created for that branch.
7. Review branch occupancy and revenue in the reporting workspace.

These workflows were exercised against the hosted demo database during project validation using synthetic records. For the detailed walkthrough and verification queries, see [`docs/professor-demo-runbook.md`](docs/professor-demo-runbook.md).

### Tests

Run the repository smoke tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The smoke tests do not replace integration testing against MySQL. Concurrency, rollback and access-boundary checks should be run against the target database before any formal demonstration; see [`docs/test-plan.md`](docs/test-plan.md).

## Limitations and responsible use

- This is a DBMS academic prototype, not a production hospital information system.
- It has not undergone clinical validation, formal security assessment, regulatory review or production-scale load testing.
- Do not enter actual patient names, contact details, UHIDs, diagnoses, prescriptions, medical histories or payment information.
- Features in the original case-study scope that are not implemented in the current web application should be treated as future work, not as available functions.
- The Railway demo may be unavailable or reset as hosting and demonstration data change.

## Project team

**Institution:** National Institute of Technology Delhi (NIT Delhi)  
**Department:** Computer Science and Engineering  
**Programme:** B.Tech. (CSE), 3rd Semester  
**Project code:** CSBB 204  
**Supervisor:** Dr. Shelly Sachdeva

| Student | Roll number |
| --- | --- |
| Lakshay Beniwal | 251210058 |
| Mohammad Anas | 251210067 |
| Mohammad Tabish Irfan | 251210068 |

## References

- AIIMS Online Registration System (ORS): [ors.gov.in](https://ors.gov.in/)
- All India Institute of Medical Sciences: [aiims.edu](https://www.aiims.edu/)
- Project synopsis prepared for CSBB 204, Department of Computer Science and Engineering, NIT Delhi.
- ER diagram prepared for the current AIIMS Connect schema.
