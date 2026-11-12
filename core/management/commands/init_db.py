"""MySQL bazasini (bo'lmasa) yaratadi: python manage.py init_db"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "MySQL bazasini yaratadi"
    requires_system_checks = []

    def handle(self, *args, **opts):
        db = settings.DATABASES["default"]
        if "sqlite" in db["ENGINE"]:
            self.stdout.write("SQLite ishlatilmoqda, baza yaratish shart emas.")
            return
        import pymysql

        conn = pymysql.connect(host=db["HOST"], port=int(db["PORT"]), user=db["USER"], password=db["PASSWORD"])
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db['NAME']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        conn.close()
        self.stdout.write(self.style.SUCCESS(f"Baza tayyor: {db['NAME']}"))
