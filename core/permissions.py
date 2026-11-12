"""Ruxsatlar tizimi.

Ikki qatlam:
1) Ko'rish doirasi (qaysi tumanlar): administrator, viloyat hodimi va tuman rahbari - butun viloyat;
   tuman hodimi - faqat o'z tumani.
2) Bo'lim va amaliyotlar: har bir bo'limda alohida amaliyotlar (ko'rish, yuklab olish, tahrirlash...).
   Rolga qarab standart ruxsatlar beriladi, administrator har bir hodim uchun ularni
   qo'shishi yoki olib qo'yishi mumkin (Profil.ruxsatlar da faqat farqlar saqlanadi).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Profil

# (kod, nomi, [(amal, nomi)], faqat_admin)
BOLIMLAR = [
    ("bosh", "Bosh panel", [("korish", "Ko'rish")], False),
    ("dinamika", "Dinamika jadvallari", [("korish", "Ko'rish"), ("eksport", "Excel / PDF yuklab olish"), ("telegram", "Telegram guruhlarga yuborish")], False),
    ("resp_dinamika", "Respublika dinamikasi", [("korish", "Ko'rish"), ("eksport", "Excel / PDF yuklab olish"), ("telegram", "Telegram guruhlarga yuborish"), ("kunlar", "Kunlarni belgilash (ish / dam olish)")], False),
    ("royxat", "Nomma-nom ro'yxat", [("korish", "Ko'rish"), ("eksport", "Excelga yuklab olish")], False),
    ("xarita", "Xarita", [("korish", "Ko'rish")], False),
    ("yuklash", "Fayl yuklash", [("korish", "Yuklamalar ro'yxatini ko'rish"), ("yuklash", "Fayl yuklash"), ("ochirish", "Yuklamani o'chirish")], False),
    ("resp_yuklash", "Respublika: fayl yuklash", [("korish", "Sahifani ko'rish"), ("yuklash", "PDF yuklash")], False),
    ("resp_fayllar", "Respublika: yuklangan PDF lar (Respublika PDF yuklash sahifasida)", [("yuklab", "Asl PDF ni yuklab olish"), ("ochirish", "Faylni o'chirish")], False),
    ("brigadalar", "Brigadalar", [("korish", "Ko'rish"), ("yaratish", "Yangi brigada qo'shish"), ("tahrirlash", "Tahrirlash"), ("ochirish", "O'chirish")], False),
    ("tp_kochirish", "TP larni ko'chirish", [("korish", "Ko'rish"), ("kochirish", "TP larni ko'chirish")], False),
    ("foydalanuvchilar", "Foydalanuvchilar", [("korish", "Ko'rish"), ("yaratish", "Yangi foydalanuvchi"), ("tahrirlash", "Tahrirlash (rol va ruxsatlar)")], True),
    ("sozlamalar", "Sozlamalar (Telegram bot)", [("korish", "Ko'rish"), ("tahrirlash", "Bot tokeni va guruhlarni sozlash")], True),
]

BARCHA = [f"{b}.{a}" for b, _n, amallar, _fa in BOLIMLAR for a, _an in amallar]
FAQAT_ADMIN = {f"{b}.{a}" for b, _n, amallar, fa in BOLIMLAR if fa for a, _an in amallar}

_OQISH = {"bosh.korish", "dinamika.korish", "dinamika.eksport", "royxat.korish", "royxat.eksport", "xarita.korish"}
ROL_STANDART = {
    "admin": set(BARCHA),
    "viloyat": set(_OQISH),
    "tuman_rahbar": set(_OQISH),
    "tuman_hodim": set(_OQISH),
}

# bosh sahifaga ruxsat bo'lmasa, o'tkaziladigan sahifalar (url nomi)
SAHIFALAR = [("bosh", "bosh"), ("dinamika", "dinamika"), ("resp_dinamika", "resp_dinamika"), ("royxat", "royxat"), ("xarita", "xarita"),
             ("yuklash", "yuklash"), ("resp_yuklash", "resp_yuklash"), ("brigadalar", "brigadalar"), ("tp_kochirish", "tp_kochirish"), ("foydalanuvchilar", "foydalanuvchilar"), ("sozlamalar", "sozlamalar")]


def profil(user):
    if not user.is_authenticated:
        return None
    try:
        return user.profil
    except Profil.DoesNotExist:
        return Profil.objects.create(user=user, rol="admin" if user.is_superuser else "tuman_hodim")


def is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = profil(user)
    return bool(p and p.rol == "admin")


def standart(rol):
    return set(ROL_STANDART.get(rol, ROL_STANDART["tuman_hodim"]))


def ruxsatlar(user):
    """Foydalanuvchining amaldagi ruxsatlari: {'bolim.amal', ...} (so'rov davomida keshlanadi)."""
    if not user.is_authenticated:
        return set()
    kesh = getattr(user, "_ruxsat_kesh", None)
    if kesh is not None:
        return kesh
    if is_admin(user):
        res = set(BARCHA)
    else:
        p = profil(user)
        res = standart(p.rol if p else "tuman_hodim")
        for kod, qiymat in ((p.ruxsatlar or {}) if p else {}).items():
            if kod not in BARCHA or kod in FAQAT_ADMIN:
                continue
            if qiymat:
                res.add(kod)
            else:
                res.discard(kod)
        res -= FAQAT_ADMIN
        # bo'limni ko'rish ruxsati bo'lmasa, uning amaliyotlari ham ishlamaydi
        res = {k for k in res if k.endswith(".korish") or k.split(".")[0] + ".korish" in res}
    user._ruxsat_kesh = res
    return res


def bor(user, kod):
    return kod in ruxsatlar(user)


def birinchi_sahifa(user):
    for bolim, url in SAHIFALAR:
        if bor(user, bolim + ".korish"):
            return url
    return None


def tuman_ids(user):
    """None = hamma tuman; aks holda ruxsat etilgan tuman id lari ro'yxati."""
    if is_admin(user):
        return None
    p = profil(user)
    if p and p.rol in ("viloyat", "tuman_rahbar"):
        return None
    if p and p.tuman_id:
        return [p.tuman_id]
    return []


def rol_nomi(user):
    if user.is_superuser:
        return "Administrator"
    p = profil(user)
    return p.get_rol_display() if p else ""


def tuman_ruxsati(user, tuman_id):
    ids = tuman_ids(user)
    return ids is None or (tuman_id in ids)


def ruxsat_kerak(kod):
    """Dekorator: kirgan va 'bolim.amal' ruxsati bor foydalanuvchi uchun."""
    def deko(view):
        @wraps(view)
        @login_required
        def wrapper(request, *a, **kw):
            if not bor(request.user, kod):
                raise PermissionDenied
            return view(request, *a, **kw)

        return wrapper

    return deko


def admin_kerak(view):
    @wraps(view)
    @login_required
    def wrapper(request, *a, **kw):
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *a, **kw)

    return wrapper
