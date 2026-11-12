# Database deployment notes

The Flask application targets the existing AIIMS Connect schema exported from MySQL 8.0.46: 15 tables, seven views, 11 stored procedures and 14 triggers.

- Your populated local database is the source of truth. The application does not run DDL or migrate it.
- Never import a structure bootstrap into your existing local database.
- To prepare an empty Railway database, run scripts/prepare_railway_schema.py against the structure-only mysqldump. It generates CREATE statements only, excludes rows, strips DROP statements and local DEFINER accounts.
- Import the generated file only into a new, empty Railway schema.
- scripts/init_db.py is a read-only schema verifier.
- scripts/seed_demo.py defaults to preview; use --apply only when the database contains synthetic demonstration/test records.
- The old generic SQL schema/seed/admin setup files have been removed because they target a different schema.
