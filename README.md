# AIIMS Connect

**One Patient. One ID. Every Branch.**

AIIMS Connect is an academic multi-branch hospital management prototype built with Flask, MySQL, Bootstrap and Chart.js. It demonstrates shared patient identity, branch-aware workflows, appointments, admissions, referrals, prescriptions and billing.

> This is an educational prototype, not an official AIIMS system and not suitable for real clinical or patient data.

## Local setup

1. Install Python 3.11+ and MySQL 8.x.
2. Create the `aiims_connect` database and run the SQL scripts under `sql/` in the documented order.
3. Copy `.env.example` to `.env` and set the database credentials and a strong Flask secret key.
4. Install dependencies with `python -m pip install -r requirements.txt`.
5. Initialise and seed the database using the scripts in `scripts/`.
6. Start the application with `python run.py` and visit `http://127.0.0.1:5000`.

## Configuration

The application reads MySQL settings from environment variables. Never commit `.env`, credentials, production secrets, or real patient information. Use synthetic demo data only.

## Tests

Run the included smoke tests with:

```bash
python -m unittest discover -s tests -v
```

These tests do not replace MySQL integration, concurrency, security, or clinical validation.

## Deployment

The project includes a Gunicorn `Procfile` for Python hosting platforms. Configure `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `FLASK_SECRET_KEY` in the hosting provider's environment settings. Provision a managed MySQL 8.x database separately and initialise it with the SQL scripts.
