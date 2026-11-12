@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo  Hodimlar nazorati - birinchi o'rnatish
echo ==============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [XATO] Python topilmadi. Python o'rnatilganini va PATH ga qo'shilganini tekshiring.
  pause
  exit /b 1
)

if not exist venv (
  echo [1/6] Virtual muhit yaratilmoqda...
  python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/6] Kutubxonalar o'rnatilmoqda...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo [XATO] Kutubxonalarni o'rnatib bo'lmadi.
  pause
  exit /b 1
)

if not exist .env (
  echo [3/6] .env fayli yaratilmoqda...
  python tools\make_env.py
)

echo [4/6] MySQL bazasi yaratilmoqda...
python manage.py init_db
if errorlevel 1 (
  echo [XATO] MySQL ga ulanib bo'lmadi. MySQL xizmati ishlayotganini va .env dagi DB_* qiymatlarini tekshiring.
  pause
  exit /b 1
)

echo [5/6] Jadvallar yaratilmoqda...
python manage.py migrate --noinput
python manage.py collectstatic --noinput

echo [6/6] Administrator yaratilmoqda...
python manage.py init_admin

echo.
echo ==============================================
echo  TAYYOR! Ishga tushirish: run.bat
echo  Kirish: login = admin   parol = Admin@12345
echo  (kirgach darhol parolni almashtiring)
echo ==============================================
pause
