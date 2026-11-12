@echo off
cd /d "%~dp0"
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo Edit .env, then run py scripts\init_db.py and py scripts\seed_demo.py
pause
