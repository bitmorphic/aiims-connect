# Database schema and deployment

The repository includes [schema.sql](schema.sql), a portable, structure-only bootstrap for the current AIIMS Connect database.

## Schema inventory

- 15 InnoDB tables
- 7 views
- 11 stored procedures
- 14 triggers

The SQL file contains no patient rows, user credentials, appointments, prescriptions, admissions, referrals or billing rows. It has no hard-coded `USE` statement, no `DROP` statements and uses lower-case table references in triggers and procedures for compatibility with Linux MySQL installations.

## Fresh database setup

1. Create a **new, empty** MySQL database (for example, `aiims_connect` locally).
2. Select that database in MySQL Workbench.
3. Execute `schema.sql` exactly once.
4. Configure the Flask environment variables for the selected database.
5. Run the read-only verifier:

   ```powershell
   .\.venv\Scripts\python.exe scripts\init_db.py
   ```

Never execute the bootstrap against an existing or populated database. It creates database objects only; it does not migrate data.

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

`scripts/prepare_railway_schema.py` is an optional utility for rebuilding a CREATE-only bootstrap from a different structure-only MySQL Workbench export. The standard repository setup does not require an external dump. The generator rejects exports containing the mysqldump table-data section and validates the expected object inventory.
