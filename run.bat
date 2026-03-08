@echo off
REM run.bat — Lanzador para Windows Task Scheduler
REM Activa el entorno virtual y ejecuta main.py con logging a archivo

cd /d "%~dp0"
call .venv\Scripts\activate

if not exist ".tmp" mkdir .tmp

python main.py >> .tmp\workana_monitor.log 2>&1
