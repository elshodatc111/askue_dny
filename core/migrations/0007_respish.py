import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0006_telegram"),
    ]

    operations = [
        migrations.CreateModel(
            name="RespIsh",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fayl_nomi", models.CharField(max_length=255)),
                ("hajm", models.PositiveIntegerField(default=0)),
                ("holat", models.CharField(choices=[("navbatda", "Navbatda"), ("jarayonda", "O'qilmoqda"), ("tayyor", "O'qildi"), ("ogoh", "Ogohlantirish bor"), ("xato", "Xato")], default="navbatda", max_length=10)),
                ("bosqich", models.CharField(blank=True, max_length=120)),
                ("foiz", models.PositiveSmallIntegerField(default=0)),
                ("sana", models.DateField(blank=True, null=True)),
                ("xabar", models.TextField(blank=True)),
                ("almashdi", models.BooleanField(default=False)),
                ("vaqt", models.DateTimeField(auto_now_add=True)),
                ("tugadi", models.DateTimeField(blank=True, null=True)),
                ("yuklagan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Respublika PDF o'qish jarayoni", "verbose_name_plural": "Respublika PDF o'qish jarayonlari", "ordering": ["-id"]},
        ),
    ]
