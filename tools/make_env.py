"""setup.bat uchun: .env.example dan .env yaratadi va tasodifiy SECRET_KEY yozadi."""
import pathlib
import secrets

base = pathlib.Path(__file__).resolve().parent.parent
matn = (base / ".env.example").read_text(encoding="utf-8")
matn = matn.replace("SECRET_KEY=bu-yerga-uzun-tasodifiy-matn-yozing", "SECRET_KEY=" + secrets.token_urlsafe(50))
(base / ".env").write_text(matn, encoding="utf-8")
print(".env yaratildi")
