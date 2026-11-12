"""Buyruq qatoridan import: python manage.py import_files fayl1.xlsx fayl2.xlsx --sana 2026-11-12"""
import datetime
import os
import shutil
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Yuklama
from core.services import importer


class Command(BaseCommand):
    help = "CAS Excel fayllarini import qiladi"

    def add_arguments(self, parser):
        parser.add_argument("fayllar", nargs="+")
        parser.add_argument("--sana", help="YYYY-MM-DD (bo'lmasa fayldan yoki bugun)")

    def handle(self, *args, **o):
        forma = datetime.date.fromisoformat(o["sana"]) if o.get("sana") else None
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ishlar = []
        for f in o["fayllar"]:
            yol = os.path.join(settings.UPLOAD_DIR, uuid.uuid4().hex + ".xlsx")
            shutil.copy(f, yol)
            info = importer.aniqlash(yol, os.path.basename(f))
            sana = forma or info["sana"] or datetime.date.today()
            y = Yuklama.objects.create(tur=info["tur"], sana=sana, fayl_nomi=os.path.basename(f)[:255], holat="jarayonda")
            ishlar.append({"yuklama_id": y.id, "path": yol, "header": info["header"], "tur": info["tur"]})
            self.stdout.write(f"{f}: {info['tur']} {sana}")
        importer.sinxron(ishlar)
        for ish in ishlar:
            try:
                os.remove(ish["path"])
            except OSError:
                pass
            y = Yuklama.objects.get(pk=ish["yuklama_id"])
            self.stdout.write(f"  -> {y.get_tur_display()} {y.sana}: {y.holat} | {y.xabar[:200]}")
