# AIIMS Connect
**One Patient. One ID. Every Branch.**

Academic multi-branch hospital management prototype: Flask + MySQL 8.4 + Bootstrap + Chart.js. Synthetic data only; not an official AIIMS system or production clinical software.

## Windows setup
1. Install Python 3.11+ and MySQL 8.4.
2. In MySQL Workbench, run `sql/admin_setup.sql` using your administrator account. It creates `aiims_connect` and grants database-scoped privileges to `aiims_app`. If the user already exists, its password is not changed.
3. Copy `.env.example` to `.env`, then enter your `aiims_app` password and a random Flask secret.
4. Run `setup.bat`, then `py scripts/init_db.py`, `py scripts/seed_demo.py`, and `py run.py`.
5. Open http://127.0.0.1:5000.

Demo usernames: `chainadmin`, `delhiadmin`, `doctor1`, `reception1`, `patient1`. Password for all: `Demo@12345`.

## Tests
`py -m unittest discover -s tests -v`

The included smoke tests are not a substitute for running integration, concurrency and security tests against your local MySQL instance. Never commit `.env`. Use synthetic data only.

## Deployment (Railway / Render)
- Deploy this repository as a Python web service. The included `Procfile` starts the app with Gunicorn and binds to the platform-provided `$PORT`.
- `mise.toml` pins Python 3.12.8 and disables Mise's optional GitHub artifact-attestation verification for this Python build because the release has no attestation available for Mise to verify.
- Add a managed MySQL 8.x database. Set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in the web service environment using the database provider's private connection values.
- Set `FLASK_SECRET_KEY` to a long, random secret and set `FLASK_DEBUG=0`.
- Initialise the hosted database once by running the SQL files in this order: `sql/schema.sql`, `sql/triggers.sql`, `sql/procedures.sql`, `sql/views.sql`, `sql/roles.sql`, then `sql/seed.sql` if demo data is wanted. Review `sql/admin_setup.sql` before using it; it is intended for a MySQL administrator and local account provisioning.
- Do not commit `.env`, database credentials, real patient information, or production secrets. Use synthetic demo data only.

The project is an academic prototype. It has not been security-audited or validated for real clinical or patient data.
