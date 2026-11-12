@echo off
chcp 65001 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
set DEBUG=1
python manage.py runserver 0.0.0.0:8000
pause
