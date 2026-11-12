# AIIMS Connect

**One Patient. One ID. Every Branch.**

AIIMS Connect is an academic multi-branch hospital operations prototype built with Flask, MySQL, Bootstrap and Chart.js. It uses a single patient UHID across branches and demonstrates outpatient appointments, inpatient admissions, prescriptions, inter-branch referrals, billing and aggregate reporting.

> Independent academic prototype. It is not affiliated with AIIMS or the Government of India and is not designed for real clinical use. Use synthetic demonstration records only.

## The database schema this application targets

The Flask application is adapted to the existing AIIMS Connect schema exported from MySQL 8.0.46. It expects these 15 tables: `admin_staff`, `admission`, `appointment`, `audit_log`, `billing`, `branch`, `department`, `doctor`, `login`, `patient`, `prescription`, `receptionist`, `referral`, `staff`, and `ward`.

It also uses these seven views: `branch_revenue_view`, `branch_ward_view`, `chain_occupancy_view`, `doctor_schedule_view`, `patient_history_view`, `patient_self_view`, and `referral_flow_view`; 11 stored procedures; and 14 triggers. The application calls the existing stored procedures for registration, booking, cancellation, completion, admission, discharge/billing, prescriptions, referral acceptance/rejection and bill payment.

**Do not run the old generic `schema.sql`, `seed.sql` or `admin_setup.sql` from earlier application versions.** Those were written for a different schema. The current application does not recreate or migrate your local database.

## Local Windows setup (preserve your existing MySQL database)

1. Make sure your local MySQL Server service is running and that MySQL Workbench can connect to it.
2. Clone or pull this repository:

   ```powershell
   git clone https://github.com/bitmorphic/aiims-connect.git
   cd aiims-connect
   # For an existing clone, use: git pull origin main
   ```

3. Use Python 3.12. Check with `py -0p`. Create a virtual environment and install dependencies:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Create your local environment file:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   For a local-only professor demo, set `DB_HOST=127.0.0.1`, `DB_PORT=3306`, `DB_NAME=aiims_connect`, and enter the MySQL username/password that already works on your laptop. `root` can be used for a local classroom demo if that is the account you connect with in Workbench; do not use a root account for a public production database. Generate a fresh `FLASK_SECRET_KEY` with:

   ```powershell
   py -3.12 -c "import secrets; print(secrets.token_hex(32))"
   ```

5. Verify the current database **without changing it**:

   ```powershell
   .\.venv\Scripts\python.exe scripts\init_db.py
   ```

   This script is read-only. It checks for the 15 tables, seven views, 11 procedures and 14 triggers expected by this application. It does not create, drop, seed or alter database objects.

6. Optional: preview a small synthetic data top-up. The default command is read-only:

   ```powershell
   .\.venv\Scripts\python.exe scripts\seed_demo.py
   ```

   Only after confirming the connected database contains demo/test data, apply the optional top-up:

   ```powershell
   .\.venv\Scripts\python.exe scripts\seed_demo.py --apply
   ```

   The script only adds synthetic records using the existing stored procedures and schema constraints; it never updates or deletes existing rows. Its modest targets are up to 40 patients, 55 appointments, 30 prescriptions, 18 admissions, 12 bills and 10 referrals. It tops up only the missing counts; if your current count is already higher, it leaves it alone. New demo patient accounts use password `Demo@12345` and usernames `demo.patient.01`, `demo.patient.02`, etc. The script does not reset existing account passwords. Do not run it against a database containing real patient records.

7. Start Flask:

   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

   Open `http://127.0.0.1:5000`. Keep the PowerShell window open while testing.

## Existing login accounts

The application reads the accounts already present in your `login` table and maps the database roles as follows:

- `Admin` + `admin_staff.Access_Level='Chain'` → Chain Admin
- `Admin` + `admin_staff.Access_Level='Branch'` → Branch Admin
- `Doctor` → Doctor
- `Receptionist` → Receptionist
- `Patient` → Patient

The app does not replace or reset your existing usernames/passwords. Use the credentials already stored in your local database. Optional newly seeded demo patients use `Demo@12345` as described above. If the script initializes a completely empty demo network, it also creates synthetic staff accounts (all using `Demo@12345`): `chain.admin`, `admin.delhi`, `admin.jodhpur`, `admin.bhopal`; `doctor.delhi.01`–`.04`, `doctor.jodhpur.01`–`.04`, `doctor.bhopal.01`–`.04`; and `reception.delhi.01`, `reception.delhi.02`, `reception.jodhpur.01`, `reception.bhopal.01`. These are demonstration identities, not real AIIMS staff.

## Railway deployment with MySQL Workbench

For the public Railway site, the Flask service must use the Railway MySQL service. Do not configure the Railway app with `localhost`; inside Railway, `localhost` would refer to the Flask container itself.

1. Create a Railway MySQL service and a Flask web service connected to this repository.
2. In the Flask service, map Railway's private MySQL variables to the application's expected variables:
   - `DB_HOST` = `${{MySQL.MYSQLHOST}}`
   - `DB_PORT` = `${{MySQL.MYSQLPORT}}`
   - `DB_USER` = `${{MySQL.MYSQLUSER}}`
   - `DB_PASSWORD` = `${{MySQL.MYSQLPASSWORD}}`
   - `DB_NAME` = the database name you imported the schema into (often `${{MySQL.MYSQLDATABASE}}` if you keep Railway's default database name)
   - `FLASK_SECRET_KEY` = a fresh random secret
   - `FLASK_DEBUG` = `0`
   - `COOKIE_SECURE` = `1`

   Replace `MySQL` in the references with the exact Railway database service name.

3. Generate a clean bootstrap from your structure-only export with `py scripts/prepare_railway_schema.py aiims_connect_structure.sql aiims_connect_railway_schema.sql`. Import the generated `aiims_connect_railway_schema.sql` **only into a new, empty Railway database/schema**. In Workbench, connect to Railway's MySQL TCP Proxy, select the empty schema, open the generated file, and execute the whole script. The file contains structure only: no local patient rows, logins, appointments or transactions. If Railway's database is named something other than `aiims_connect`, select that schema in Workbench before execution. The importing MySQL account becomes the definer for the imported triggers, views and stored procedures.
4. Run the read-only verification script against the new Railway database by temporarily using its connection variables locally, or use Workbench's `SHOW TABLES`, `SHOW FULL TABLES WHERE Table_type='VIEW'`, `SHOW PROCEDURE STATUS WHERE Db=DATABASE()`, and `SHOW TRIGGERS` commands.
5. Seed only synthetic demo records in the new Railway DB by pointing a temporary local `.env` at the Railway connection and running `scripts/seed_demo.py` (preview first, then `--apply`). Do not seed or migrate any actual patient records.
6. Deploy the Flask service. Its `Procfile` starts Gunicorn and binds to Railway's `$PORT`.
7. To watch live writes, enable Railway MySQL TCP Proxy under the database service's Settings → Networking. In Workbench, create a separate connection using the public proxy hostname/port and the Railway MySQL username/password/database. Keep the existing local connection as a separate saved connection. Both the Railway website and the Railway Workbench connection then see the same Railway database.

The structure-only file does not migrate your local database rows to Railway. If you want to move local records, first confirm they are all synthetic demo data and use a separately reviewed data-only export/import. Never upload real patient data.

## Application modules

- Public product landing page and sign-in
- Role-aware dashboard with branch occupancy and recent appointment activity
- Patient registry and patient self-service history
- OPD appointment booking, cancellation and completion
- Ward and bed availability
- Inpatient admission, discharge and automatic bill generation
- Doctor prescriptions
- Inter-branch referral creation, acceptance and rejection
- Billing and payment status
- Aggregate branch revenue and capacity reports
- Database audit records driven by triggers using the session variable `@app_login_id`

## Tests and limitations

Run the included smoke tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These checks do not replace running the app against your specific MySQL instance and exercising each workflow. The application and schema have not been security-audited or clinically validated. Use synthetic demo records only.
