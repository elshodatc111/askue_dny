"""Eski nomma-nom ma'lumotlarni tozalash (jamlama statistika saqlanadi): python manage.py tozalash"""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Kuzatuv


class Command(BaseCommand):
    help = "DETAIL_RETENTION_DAYS dan eski batafsil qatorlarni o'chiradi"

    def handle(self, *args, **o):
        chegara = datetime.date.today() - datetime.timedelta(days=settings.DETAIL_RETENTION_DAYS)
        n, _ = Kuzatuv.objects.filter(yuklama__sana__lt=chegara).delete()
        self.stdout.write(f"{n} ta eski qator o'chirildi ({chegara} gacha).")
