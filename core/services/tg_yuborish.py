"""Dinamika va Respublika dinamikasi fayllarini Telegram guruhlariga orqa fonda yuborish."""
import json
import re
import threading
import time

from django.db import connection
from django.utils import timezone

from ..models import RespYuklama, TelegramGuruh, TelegramIsh, TelegramSozlama, Tuman
from . import eksport
from . import resp as R
from . import resp_eksport as RE
from . import stats as S
from . import telegram as T

ORALIQ = 1.2  # bir xabardan keyingi tanaffus (sekund), Telegram chegarasiga tushmaslik uchun


def _d(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _toza(t):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", eksport._lotin(t)).strip("_") or "tuman"


def _solishtirma(a):
    return f"🔁 Solishtirish sanasi: {_d(a)}" if a else "🔁 Solishtirilmagan"


# ---------------------------------------------------------------- fayllarni tayyorlash
def dinamika_fayllari(tur, a, b, ruxsat, tuman_id):
    """Dinamika jadvali uchun [(fayl_nomi, bytes, izoh)] ro'yxati.
    tur: xlsx | pdf (tanlangan tuman/viloyat bo'yicha bitta fayl), tumanlar (har bir tuman uchun alohida PDF)."""
    def elementlar(tid, nom):
        out = []
        for k in S.SAHIFALAR:
            j = S.dinamika_sahifa(k, a, b, ruxsat, tid)
            out.append((j, {"tur_nom": S.SAHIFALAR[k][0], "a": a, "b": b, "tuman": nom, "tur": S.SAHIFA_NOM[k], "yuklangan": S.yuklangan_vaqt(S.SAHIFALAR[k][1], b)}))
        return out

    sana = b.strftime("%Y-%m-%d")
    if tur == "tumanlar":
        qs = Tuman.objects.all()
        if ruxsat is not None:
            qs = qs.filter(pk__in=ruxsat)
        for t in qs:
            nom = f"{_toza(t.korsat)}_dinamika_{_d(b)}_{_d(a) + '_bilan' if a else 'solishtirmasiz'}.pdf"
            izoh = f"📍 {t.korsat}: brigadalar kesimida dinamika\n📅 Joriy sana: {_d(b)}\n{_solishtirma(a)}"
            yield nom, eksport.kopchilik_pdf(elementlar(t.id, t.korsat)), izoh
        return
    tuman = Tuman.objects.filter(pk=tuman_id).first() if tuman_id else None
    nom_t = tuman.korsat if tuman else ""
    hudud = nom_t or "Qashqadaryo HETK"
    asos = f"dinamika_{_toza(nom_t) + '_' if nom_t else ''}{sana}"
    if tur == "xlsx":
        resp = eksport.kopchilik_xlsx(elementlar(tuman_id, nom_t), asos + ".xlsx")
        yield asos + ".xlsx", resp.content, f"📊 Dinamika jadvali (Excel)\n📍 {hudud}\n📅 Joriy sana: {_d(b)}\n{_solishtirma(a)}"
    else:
        yield asos + ".pdf", eksport.kopchilik_pdf(elementlar(tuman_id, nom_t)), f"📄 Dinamika jadvali (PDF)\n📍 {hudud}\n📅 Joriy sana: {_d(b)}\n{_solishtirma(a)}"


def resp_fayllari(tur, a, b):
    """Respublika dinamikasi uchun [(fayl_nomi, bytes, izoh)] (tur: xlsx | pdf)."""
    yb = RespYuklama.objects.filter(sana=b, faol=True).first()
    if not yb:
        raise ValueError("Tanlangan sana uchun respublika hisoboti topilmadi.")
    ya = RespYuklama.objects.filter(sana=a, faol=True).first() if a else None
    data = json.loads(yb.malumot)
    baza = json.loads(ya.malumot) if ya else None
    meta = {"sana": b, "baza": a if ya else None, "yuklangan": yb.vaqt}
    jadvallar = R.barcha_jadvallar(data, baza)
    izoh_oxiri = f"\n📅 Hisobot sanasi: {_d(b)}\n{_solishtirma(a if ya else None)}"
    if tur == "xlsx":
        yield RE.fayl_nomi(meta, "xlsx"), RE.xlsx(jadvallar, meta), "📊 Respublika dinamikasi (Excel)" + izoh_oxiri
    else:
        yield RE.fayl_nomi(meta, "pdf"), RE.pdf(jadvallar, meta), "📄 Respublika dinamikasi (PDF)" + izoh_oxiri


# ---------------------------------------------------------------- yuborish
def _yangila(ish, **kw):
    for k, v in kw.items():
        setattr(ish, k, v)
    ish.save(update_fields=list(kw))


def _bajar(ish_id, guruh_idlar, fayllar_fn):
    """Orqa fon oqimi: fayllarni tayyorlaydi va tanlangan guruhlarga birma-bir yuboradi."""
    try:
        ish = TelegramIsh.objects.get(pk=ish_id)
        try:
            token = TelegramSozlama.olish().bot_token
            guruhlar = list(TelegramGuruh.objects.filter(pk__in=guruh_idlar, faol=True))
            if not token:
                raise ValueError("Bot tokeni kiritilmagan.")
            if not guruhlar:
                raise ValueError("Yuborish uchun faol guruh topilmadi.")
            fayllar = list(fayllar_fn())
            if not fayllar:
                raise ValueError("Yuboriladigan fayl yo'q.")
            _yangila(ish, jami=len(fayllar) * len(guruhlar))
            xatolar, ok, xato = [], 0, 0
            for nom, data, izoh in fayllar:
                for g in guruhlar:
                    try:
                        _res, yangi = T.hujjat_yubor(token, g.chat_id, nom, data, izoh)
                        if yangi != g.chat_id:  # guruh supergruppaga aylangan
                            g.chat_id = yangi
                            g.save(update_fields=["chat_id"])
                        ok += 1
                    except T.TgXato as e:
                        xato += 1
                        if len(xatolar) < 30:
                            xatolar.append(f"{g.nom} · {nom}: {e}")
                    _yangila(ish, yuborildi=ok, xato_soni=xato)
                    time.sleep(ORALIQ)
            holat = "tayyor" if not xato else ("xato" if not ok else "qisman")
            _yangila(ish, holat=holat, xabar="\n".join(xatolar), tugadi=timezone.now())
        except Exception as e:  # noqa
            _yangila(ish, holat="xato", xabar=str(e)[:2000], tugadi=timezone.now())
    finally:
        connection.close()


def fonda_boshlash(ish_id, guruh_idlar, fayllar_fn):
    t = threading.Thread(target=_bajar, args=(ish_id, guruh_idlar, fayllar_fn), daemon=True)
    t.start()
    return t
