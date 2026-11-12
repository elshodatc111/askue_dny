@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist venv (
  echo Avval setup.bat ni ishga tushiring.
  pause
  exit /b 1
)
echo pdfplumber internetsiz o'rnatilmoqda...
venv\Scripts\pip install --no-index --find-links wheels pdfplumber
if errorlevel 1 (
  echo [XATO] O'rnatib bo'lmadi.
) else (
  echo [OK] pdfplumber o'rnatildi. Endi run.bat ni ishga tushiring.
)
pause
