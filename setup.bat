@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 and its Windows launcher first.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Python 3.12 was not found. Run py -0p to check installed versions.
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo Dependencies installed.
echo Edit .env with the MySQL host, username and password that work in Workbench.
echo Verify schema: .venv\Scripts\python.exe scripts\init_db.py
echo Preview demo additions: .venv\Scripts\python.exe scripts\seed_demo.py
echo Apply only to synthetic demo data: .venv\Scripts\python.exe scripts\seed_demo.py --apply
echo Start Flask: .venv\Scripts\python.exe run.py
pause
exit /b 0
:failed
echo Setup failed. Read the error above and retry.
pause
exit /b 1
