from django.contrib.auth.models import User
from django.db import models


class Tuman(models.Model):
    """Tuman/shahar (CAS dagi ESP: TETK, ShETK, ETK)."""

    nom = models.CharField("CAS dagi nomi", max_length=120, unique=True)
    qisqa = models.CharField("Qisqa nomi", max_length=60, blank=True)
    tartib = models.PositiveIntegerField("Tartib raqami", default=100)

    class Meta:
        ordering = ["tartib", "nom"]
        verbose_name = "Tuman"
        verbose_name_plural = "Tumanlar"

    def __str__(self):
        return self.korsat

    @property
    def korsat(self):
        return self.qisqa or self.nom


class Brigada(models.Model):
    tuman = models.ForeignKey(Tuman, on_delete=models.CASCADE, related_name="brigadalar")
    raqam = models.PositiveIntegerField("Raqami", default=1)
    nom = models.CharField("Nomi", max_length=120)
    manba = models.CharField("CAS dagi mas'ullar yozuvi", max_length=500, blank=True)
    manba_kalit = models.CharField(max_length=40, blank=True, db_index=True)
    telefon = models.CharField("Telefon", max_length=200, blank=True)

    class Meta:
        ordering = ["tuman__tartib", "raqam"]
        verbose_name = "Brigada"
        verbose_name_plural = "Brigadalar"

    def __str__(self):
        return f"{self.tuman.korsat} - {self.nom}"


class Hodim(models.Model):
    brigada = models.ForeignKey(Brigada, on_delete=models.CASCADE, related_name="hodimlar")
    ism = models.CharField("F.I.Sh.", max_length=200)
    pinfl = models.CharField("JShShIR", max_length=20, blank=True)
    telefon = models.CharField("Telefon", max_length=40, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Hodim"
        verbose_name_plural = "Hodimlar"

    def __str__(self):
        return self.ism


class TP(models.Model):
    """Transformator punkti. Kalit = tuman+podstansiya+feeder+TP raqami (normallashtirilgan)."""

    tuman = models.ForeignKey(Tuman, on_delete=models.CASCADE, related_name="tplar")
    kalit = models.CharField(max_length=40, unique=True)
    podstansiya = models.CharField(max_length=150, blank=True)
    feeder = models.CharField(max_length=150, blank=True)
    raqam = models.CharField("TP raqami", max_length=60, blank=True)
    egasi = models.CharField(max_length=40, blank=True)
    brigada = models.ForeignKey(Brigada, null=True, blank=True, on_delete=models.SET_NULL, related_name="tplar")

    class Meta:
        verbose_name = "TP"
        verbose_name_plural = "TP lar"
        indexes = [models.Index(fields=["tuman", "brigada"])]

    def __str__(self):
        return f"{self.podstansiya} / {self.feeder} / {self.raqam}"


class Yuklama(models.Model):
    TURLAR = [
        ("area", "Hududiy tuzilma (TP va brigadalar)"),
        ("dcu", "Konsentratorlar"),
        ("gprs", "GPRS hisoblagichlar"),
        ("nometer", "Aloqadan chiqib ketgan hisoblagichlar"),
        ("direct", "To'g'ridan-to'g'ri ulanish (Primichka)"),
    ]
    HOLATLAR = [("jarayonda", "Jarayonda"), ("tayyor", "Tayyor"), ("xato", "Xato")]

    tur = models.CharField(max_length=10, choices=TURLAR)
    sana = models.DateField("Ma'lumot sanasi")
    fayl_nomi = models.CharField(max_length=255, blank=True)
    yuklagan = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    vaqt = models.DateTimeField("Yuklangan vaqt", auto_now_add=True)
    holat = models.CharField(max_length=10, choices=HOLATLAR, default="jarayonda")
    qatorlar = models.PositiveIntegerField(default=0)
    xabar = models.TextField(blank=True)

    class Meta:
        ordering = ["-sana", "-vaqt"]
        verbose_name = "Yuklama"
        verbose_name_plural = "Yuklamalar"
        indexes = [models.Index(fields=["tur", "sana", "holat"])]

    def __str__(self):
        return f"{self.get_tur_display()} - {self.sana:%d.%m.%Y}"


class Kuzatuv(models.Model):
    """Nomma-nom ro'yxat qatori: offline DCU/GPRS, aloqadan chiqib ketgan hisoblagich, direct (kun bo'yicha)."""

    yuklama = models.ForeignKey(Yuklama, on_delete=models.CASCADE, related_name="kuzatuvlar")
    tp = models.ForeignKey(TP, on_delete=models.CASCADE, related_name="kuzatuvlar")
    raqam = models.CharField("Qurilma raqami", max_length=40, db_index=True)
    kun = models.IntegerField("Necha kun", null=True, blank=True)
    vaqt = models.DateTimeField("Oxirgi aloqa vaqti", null=True, blank=True)
    abonent = models.CharField(max_length=200, blank=True)
    hisob = models.CharField(max_length=40, blank=True)
    abonent_turi = models.CharField(max_length=10, blank=True)  # aholi / ulgurji / balans / boshqa
    aloqa_turi = models.CharField(max_length=10, blank=True)  # PLC / GPRS / RS485
    manzil = models.CharField(max_length=300, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    operator = models.CharField(max_length=30, blank=True)
    ip = models.CharField(max_length=45, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["yuklama", "kun"]),
            models.Index(fields=["yuklama", "raqam"]),
        ]


class TPSana(models.Model):
    """Har bir kun va TP uchun jamlama. Tuman/brigada statistikasi shundan yig'iladi."""

    yuklama = models.ForeignKey(Yuklama, on_delete=models.CASCADE, related_name="jamlamalar")
    tp = models.ForeignKey(TP, on_delete=models.CASCADE, related_name="jamlamalar")
    jami = models.PositiveIntegerField(default=0)
    online = models.PositiveIntegerField(default=0)
    b0 = models.PositiveIntegerField(default=0)  # 1 kungacha
    b1 = models.PositiveIntegerField(default=0)  # 2-7
    b2 = models.PositiveIntegerField(default=0)  # 7-30
    b3 = models.PositiveIntegerField(default=0)  # 30-90
    b4 = models.PositiveIntegerField(default=0)  # 90+
    aholi = models.PositiveIntegerField(default=0)
    ulgurji = models.PositiveIntegerField(default=0)
    balans = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["yuklama", "tp"])]


class Profil(models.Model):
    ROLLAR = [
        ("admin", "Administrator"),
        ("viloyat", "Viloyat hodimi"),
        ("tuman_rahbar", "Tuman rahbari"),
        ("tuman_hodim", "Tuman hodimi"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profil")
    rol = models.CharField(max_length=15, choices=ROLLAR, default="tuman_hodim")
    tuman = models.ForeignKey(Tuman, null=True, blank=True, on_delete=models.SET_NULL, help_text="Tuman hodimi uchun majburiy")
    telefon = models.CharField(max_length=40, blank=True)
    ruxsatlar = models.JSONField("Qo'shimcha ruxsatlar", default=dict, blank=True,
                                 help_text="Rol bo'yicha standart ruxsatdan farqlar: {'bolim.amal': true/false}")

    class Meta:
        verbose_name = "Foydalanuvchi profili"
        verbose_name_plural = "Foydalanuvchi profillari"

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"


class RespYuklama(models.Model):
    """Respublikadan kelgan kunlik dinamika PDF si va undan o'qilgan jadval ma'lumotlari."""

    HOLATLAR = [("tayyor", "Tayyor"), ("shubhali", "Tekshiruvda ogohlantirish bor")]

    sana = models.DateField("Hisobot sanasi", db_index=True)
    fayl_nomi = models.CharField(max_length=255)
    yol = models.CharField("Saqlangan joyi", max_length=500)
    hajm = models.PositiveIntegerField(default=0)
    yuklagan = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    vaqt = models.DateTimeField("Yuklangan vaqt", auto_now_add=True)
    faol = models.BooleanField("Amaldagi", default=True)
    holat = models.CharField(max_length=10, choices=HOLATLAR, default="tayyor")
    xabar = models.TextField(blank=True)
    malumot = models.TextField(blank=True)  # JSON: {bet_kodi: [qatorlar]}

    class Meta:
        ordering = ["-sana", "-vaqt"]
        verbose_name = "Respublika yuklamasi"
        verbose_name_plural = "Respublika yuklamalari"
        indexes = [models.Index(fields=["sana", "faol"])]

    def __str__(self):
        return f"Respublika dinamikasi {self.sana:%d.%m.%Y}"


class RespKun(models.Model):
    """Kunni qo'lda belgilash: ish kuni (ko'rsatiladi) yoki dam olish kuni (ko'rsatilmaydi).
    Belgi yo'q kunlarda shanba va yakshanba dam olish kuni hisoblanadi."""

    sana = models.DateField(unique=True)
    ish = models.BooleanField(default=True)
    izoh = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-sana"]
        verbose_name = "Belgilangan kun"
        verbose_name_plural = "Belgilangan kunlar"

    def __str__(self):
        return f"{self.sana:%d.%m.%Y} - {'ish kuni' if self.ish else 'dam olish kuni'}"


class TelegramSozlama(models.Model):
    """Telegram bot sozlamasi (bitta yozuv): bot tokeni."""

    bot_token = models.CharField("Bot tokeni", max_length=200, blank=True)
    bot_nomi = models.CharField("Bot nomi (@username)", max_length=120, blank=True)

    class Meta:
        verbose_name = "Telegram sozlamasi"
        verbose_name_plural = "Telegram sozlamasi"

    def __str__(self):
        return f"Telegram bot {self.bot_nomi}".strip()

    @classmethod
    def olish(cls):
        obj = cls.objects.order_by("id").first()
        return obj or cls.objects.create()


class TelegramGuruh(models.Model):
    """Bot admin qilib biriktirilgan guruh (yoki kanal)."""

    nom = models.CharField("Guruh nomi", max_length=200)
    chat_id = models.CharField("Chat ID", max_length=40, unique=True)
    tur = models.CharField("Turi", max_length=20, blank=True)
    faol = models.BooleanField("Yuborish yoqilgan", default=True)
    qoshilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "id"]
        verbose_name = "Telegram guruhi"
        verbose_name_plural = "Telegram guruhlari"

    def __str__(self):
        return self.nom


class TelegramIsh(models.Model):
    """Telegramga yuborish jarayoni (orqa fonda bajariladi)."""

    HOLATLAR = [("jarayonda", "Yuborilmoqda"), ("tayyor", "Yuborildi"), ("qisman", "Qisman yuborildi"), ("xato", "Xato")]

    sarlavha = models.CharField(max_length=200)
    holat = models.CharField(max_length=12, choices=HOLATLAR, default="jarayonda")
    jami = models.PositiveIntegerField("Jami xabarlar", default=0)
    yuborildi = models.PositiveIntegerField("Yuborildi", default=0)
    xato_soni = models.PositiveIntegerField("Xatolar", default=0)
    xabar = models.TextField(blank=True)
    yaratgan = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    vaqt = models.DateTimeField(auto_now_add=True)
    tugadi = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-vaqt"]
        verbose_name = "Telegram yuborish"
        verbose_name_plural = "Telegram yuborishlar"

    def __str__(self):
        return self.sarlavha


class RespIsh(models.Model):
    """Respublika PDF sini orqa fonda o'qish jarayoni (yuklash sahifasida jonli ko'rsatiladi)."""

    HOLATLAR = [("navbatda", "Navbatda"), ("jarayonda", "O'qilmoqda"), ("tayyor", "O'qildi"), ("ogoh", "Ogohlantirish bor"), ("xato", "Xato")]

    fayl_nomi = models.CharField(max_length=255)
    hajm = models.PositiveIntegerField(default=0)
    holat = models.CharField(max_length=10, choices=HOLATLAR, default="navbatda")
    bosqich = models.CharField(max_length=120, blank=True)
    foiz = models.PositiveSmallIntegerField(default=0)
    sana = models.DateField(null=True, blank=True)
    xabar = models.TextField(blank=True)  # xato matni yoki ogohlantirishlar (har biri yangi qatorda)
    almashdi = models.BooleanField(default=False)
    yuklagan = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    vaqt = models.DateTimeField(auto_now_add=True)
    tugadi = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Respublika PDF o'qish jarayoni"
        verbose_name_plural = "Respublika PDF o'qish jarayonlari"

    def __str__(self):
        return f"{self.fayl_nomi} ({self.get_holat_display()})"
