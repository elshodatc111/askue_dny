@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist venv (
  echo Avval setup.bat ni ishga tushiring.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python manage.py migrate --noinput
python manage.py collectstatic --noinput >nul
echo.
echo Server ishga tushdi: http://localhost:8765
echo (to'xtatish uchun Ctrl+C)
echo Cloudflare tunnel manzili: http://localhost:8765
waitress-serve --listen=0.0.0.0:8765 --threads=8 --channel-timeout=300 config.wsgi:application
pause
