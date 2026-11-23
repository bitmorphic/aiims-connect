# Database schema and deployment

The repository includes [schema.sql](schema.sql), a portable, structure-only bootstrap for the current AIIMS Connect database.

## Schema inventory

- 17 tables (15 operational tables plus 2 FHIR interoperability tables)
- 7 views
- 11 stored procedures
- 14 triggers

The SQL file contains no patient rows, user credentials, appointments, prescriptions, admissions, referrals, billing rows or imported FHIR resources. It has no hard-coded `USE` statement, no `DROP` statements and uses lower-case table references in triggers and procedures for compatibility with Linux MySQL installations.

## Fresh database setup

1. Create a **new, empty** MySQL database (for example, `aiims_connect` locally).
2. Select that database in MySQL Workbench.
3. Execute `schema.sql` exactly once.
4. Configure the Flask environment variables for the selected database.
5. Run the read-only verifier:

   ```powershell
   .\.venv\Scripts\python.exe scripts\init_db.py
   ```

Never execute the bootstrap against an existing or populated database. It creates database objects only; it does not migrate operational data or import the Synthea FHIR ZIP.

## Synthetic demonstration data

`scripts/seed_demo.py` is preview-only by default:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

Review the proposed top-up, then apply it only to a database containing synthetic academic/demo records:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --apply
```

Do not use the seeder with real patient information.

## Custom schema exports

`scripts/prepare_railway_schema.py` is an optional utility for rebuilding a CREATE-only bootstrap from a different structure-only MySQL Workbench export. The standard repository setup does not require an external dump. The generator rejects exports containing the mysqldump table-data section and validates the expected object inventory (17 tables, including the two FHIR tables after migration).

## Existing database migrations and FHIR import

For an existing populated database, apply the application migrations in `../sql/migrations/` in the order documented in the root README. The FHIR migration creates `fhir_import_batch` and `fhir_resource`; it does not import records. After the schema is ready, use `scripts/import_fhir.py` with the separately downloaded Synthea FHIR R4 ZIP. The import is deliberately manual because the archive is a data payload, not application source, and is not included in the repository or automatic Railway deploy.
