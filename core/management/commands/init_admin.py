"""Birinchi administratorni yaratadi: python manage.py init_admin [login] [parol]"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Profil


class Command(BaseCommand):
    help = "Administrator yaratadi (bo'lmasa)"

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", default="admin")
        parser.add_argument("password", nargs="?", default="Admin@12345")

    def handle(self, *args, **o):
        u, yangi = User.objects.get_or_create(username=o["username"], defaults={"is_staff": True, "is_superuser": True, "first_name": "Administrator"})
        if yangi:
            u.set_password(o["password"])
            u.save()
        Profil.objects.update_or_create(user=u, defaults={"rol": "admin"})
        if yangi:
            self.stdout.write(self.style.SUCCESS(f"Administrator yaratildi: login={o['username']} parol={o['password']} (kirgach parolni almashtiring!)"))
        else:
            self.stdout.write(f"'{o['username']}' allaqachon mavjud.")
