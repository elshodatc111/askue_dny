import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0005_kpi_olib_tashlash"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramSozlama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bot_token", models.CharField(blank=True, max_length=200, verbose_name="Bot tokeni")),
                ("bot_nomi", models.CharField(blank=True, max_length=120, verbose_name="Bot nomi (@username)")),
            ],
            options={"verbose_name": "Telegram sozlamasi", "verbose_name_plural": "Telegram sozlamasi"},
        ),
        migrations.CreateModel(
            name="TelegramGuruh",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=200, verbose_name="Guruh nomi")),
                ("chat_id", models.CharField(max_length=40, unique=True, verbose_name="Chat ID")),
                ("tur", models.CharField(blank=True, max_length=20, verbose_name="Turi")),
                ("faol", models.BooleanField(default=True, verbose_name="Yuborish yoqilgan")),
                ("qoshilgan", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "Telegram guruhi", "verbose_name_plural": "Telegram guruhlari", "ordering": ["nom", "id"]},
        ),
        migrations.CreateModel(
            name="TelegramIsh",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sarlavha", models.CharField(max_length=200)),
                ("holat", models.CharField(choices=[("jarayonda", "Yuborilmoqda"), ("tayyor", "Yuborildi"), ("qisman", "Qisman yuborildi"), ("xato", "Xato")], default="jarayonda", max_length=12)),
                ("jami", models.PositiveIntegerField(default=0, verbose_name="Jami xabarlar")),
                ("yuborildi", models.PositiveIntegerField(default=0, verbose_name="Yuborildi")),
                ("xato_soni", models.PositiveIntegerField(default=0, verbose_name="Xatolar")),
                ("xabar", models.TextField(blank=True)),
                ("vaqt", models.DateTimeField(auto_now_add=True)),
                ("tugadi", models.DateTimeField(blank=True, null=True)),
                ("yaratgan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Telegram yuborish", "verbose_name_plural": "Telegram yuborishlar", "ordering": ["-vaqt"]},
        ),
    ]
