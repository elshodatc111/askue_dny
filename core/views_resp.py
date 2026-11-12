"""Respublika dinamikasi bo'limi: ko'rish, PDF yuklash (yuklangan fayllar ro'yxati bilan), kunlarni belgilash, eksport."""
import datetime
import io
import json
import os
import threading
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required  # noqa: F401
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import RespIsh, RespKun, RespYuklama
from .permissions import bor, ruxsat_kerak
from .services import resp as R
from .services import resp_eksport as RE

HAFTA = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MAX_HAJM = 40 * 1024 * 1024


def _iso(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _txt(d):
    return d.strftime("%d.%m.%Y")


def _kun_yorligi(d):
    return f"{_txt(d)} · {HAFTA[d.weekday()]}"


def _resp_papka():
    return Path(settings.UPLOAD_DIR) / "respublika"


def _holat():
    """(faol yuklamalar {sana: obyekt}, belgilar {sana: ish}, ko'rinadigan kunlar [sana...])"""
    faol = {y.sana: y for y in RespYuklama.objects.filter(faol=True)}
    belgilar = {k.sana: k.ish for k in RespKun.objects.all()}
    kunlar = sorted(d for d in faol if R.ish_kuni_mi(d, belgilar))
    return faol, belgilar, kunlar


# ---------------------------------------------------------------- dinamika
@ruxsat_kerak("resp_dinamika.korish")
def resp_dinamika(request):
    faol, belgilar, kunlar = _holat()
    b = _iso(request.GET.get("b"))
    if b not in kunlar:
        b = kunlar[-1] if kunlar else None
    oldin = [d for d in kunlar if b and d < b]
    a_param = request.GET.get("a") or "oy"
    a, a_izoh = None, ""
    if b:
        if a_param == "yoq":
            a = None
        elif a_param == "old":
            a = oldin[-1] if oldin else None
            if not a:
                a_izoh = "Oldingi ish kuni ma'lumoti yo'q, o'zgarishlar ko'rsatilmaydi."
        elif a_param == "oy":
            a = next((d for d in kunlar if d.year == b.year and d.month == b.month and d < b), None)
            if not a:
                a_izoh = "Bu oyning birinchi ish kuni, oy boshiga nisbatan o'zgarish yo'q."
        else:
            x = _iso(a_param)
            a = x if x in oldin else None
    sahifa = request.GET.get("s")
    if sahifa not in R.SAHIFALAR:
        sahifa = "r1"

    data = json.loads(faol[b].malumot) if b else None
    baza = json.loads(faol[a].malumot) if a else None

    fmt_ = request.GET.get("format")
    if fmt_ in ("xlsx", "pdf"):
        if not bor(request.user, "resp_dinamika.eksport"):
            raise PermissionDenied
        if not data:
            raise Http404("Ma'lumot yo'q")
        meta = {"sana": b, "baza": a, "yuklangan": faol[b].vaqt}
        jadvallar = R.barcha_jadvallar(data, baza)
        if fmt_ == "xlsx":
            resp = HttpResponse(RE.xlsx(jadvallar, meta), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            resp["Content-Disposition"] = f'attachment; filename="{RE.fayl_nomi(meta, "xlsx")}"'
        else:
            resp = HttpResponse(RE.pdf(jadvallar, meta), content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{RE.fayl_nomi(meta, "pdf")}"'
        return resp

    jadval = R.jadval(sahifa, data, baza) if data else None
    q = request.GET.copy()
    q.pop("format", None)
    q.pop("s", None)
    hozirgi_a = a_param if a_param in ("oy", "old", "yoq") else (a.isoformat() if a else "yoq")
    ctx = {
        "jadval": jadval, "sahifa": sahifa, "tablar": [(k, f"{i}. {R.SAHIFALAR[k]['nom']}") for i, k in enumerate(R.SAHIFA_TARTIB, 1)],
        "b": b, "a": a, "a_param": hozirgi_a, "a_izoh": a_izoh,
        "b_yorlig": _kun_yorligi(b) if b else "",
        "kunlar_b": [{"iso": d.isoformat(), "txt": _kun_yorligi(d)} for d in reversed(kunlar)],
        "kunlar_a": [{"iso": d.isoformat(), "txt": _kun_yorligi(d)} for d in reversed(oldin)],
        "yuklangan": faol[b].vaqt if b else None,
        "yuklash_bor": bool(kunlar),
        "ogoh": faol[b].xabar.splitlines() if b and faol[b].holat == "shubhali" else [],
        "bq": f"b={b.isoformat()}&a={hozirgi_a}" if b else "",
    }
    if bor(request.user, "resp_dinamika.kunlar"):
        ctx["kunlar_boshqaruv"] = [
            {"iso": d.isoformat(), "txt": _kun_yorligi(d), "korinadi": d in kunlar,
             "belgi": ("ish" if belgilar[d] else "dam") if d in belgilar else "", "dam_standart": not R.standart_ish_kuni(d)}
            for d in sorted(faol, reverse=True)[:60]
        ]
    return render(request, "core/resp_dinamika.html", ctx)


@ruxsat_kerak("resp_dinamika.kunlar")
@require_POST
def resp_kun(request):
    d = _iso(request.POST.get("sana"))
    holat = request.POST.get("holat")
    if not d or holat not in ("ish", "dam", "standart"):
        messages.error(request, "Noto'g'ri so'rov.")
    else:
        if holat == "standart":
            RespKun.objects.filter(sana=d).delete()
            messages.success(request, f"{_txt(d)} standart holatga qaytarildi ({'ish' if R.standart_ish_kuni(d) else 'dam olish'} kuni).")
        else:
            RespKun.objects.update_or_create(sana=d, defaults={"ish": holat == "ish"})
            messages.success(request, f"{_txt(d)} {'ish kuni' if holat == 'ish' else 'dam olish kuni'} deb belgilandi.")
    nxt = request.POST.get("next") or ""
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "resp_dinamika")


# ---------------------------------------------------------------- yuklash
def _qabul(f, user, qol_sana=None):
    """Bitta PDF ni o'qiydi, saqlaydi. Natija lug'ati qaytaradi."""
    nom = f.name
    out = {"fayl": nom, "ok": False, "sana": None, "ogoh": [], "xabar": "", "almashdi": False}
    if not nom.lower().endswith(".pdf"):
        out["xabar"] = "Faqat PDF fayl qabul qilinadi."
        return out
    if f.size > MAX_HAJM:
        out["xabar"] = "Fayl juda katta (40 MB dan oshmasligi kerak)."
        return out
    return _oqi_va_saqla(f.read(), nom, user, qol_sana, out=out)


def _oqi_va_saqla(data, nom, user, qol_sana=None, jarayon=None, out=None):
    """PDF baytlarini o'qiydi va saqlaydi. jarayon(bosqich, foiz) - jonli holat uchun (ixtiyoriy)."""
    out = out or {"fayl": nom, "ok": False, "sana": None, "ogoh": [], "xabar": "", "almashdi": False}
    cb = (lambda i, n: jarayon(f"{i}/{n}-jadval o'qildi", 8 + int(82 * i / n))) if jarayon else None
    res = R.oqi(io.BytesIO(data), nom, cb)
    if res["xato"]:
        out["xabar"] = res["xato"]
        return out
    sana = qol_sana or res["sana"]
    if not sana:
        out["xabar"] = "Hisobot sanasi aniqlanmadi. Sanani qo'lda kiriting."
        return out
    if qol_sana and res["sana"] and qol_sana != res["sana"]:
        res["ogohlantirish"].append(f"Qo'lda kiritilgan sana ({_txt(qol_sana)}) PDF dagi sanadan ({_txt(res['sana'])}) farq qiladi.")
    if jarayon:
        jarayon("Saqlanmoqda...", 94)
    papka = _resp_papka() / f"{sana:%Y-%m}"
    os.makedirs(papka, exist_ok=True)
    fayl = papka / f"{sana:%Y-%m-%d}_{uuid.uuid4().hex[:8]}.pdf"
    with open(fayl, "wb") as w:
        w.write(data)
    with transaction.atomic():
        eski = RespYuklama.objects.filter(sana=sana, faol=True)
        out["almashdi"] = eski.exists()
        eski.update(faol=False)
        RespYuklama.objects.create(
            sana=sana, fayl_nomi=nom[:255], yol=str(fayl.relative_to(Path(settings.UPLOAD_DIR))), hajm=len(data), yuklagan=user, faol=True,
            holat="shubhali" if res["ogohlantirish"] else "tayyor", xabar="\n".join(res["ogohlantirish"][:40]), malumot=R.malumot_json(res["malumot"]))
    out.update(ok=True, sana=sana, ogoh=res["ogohlantirish"])
    return out


@ruxsat_kerak("resp_yuklash.korish")
def resp_yuklash(request):
    natijalar = []
    if request.method == "POST":
        if not bor(request.user, "resp_yuklash.yuklash"):
            raise PermissionDenied
        fayllar = request.FILES.getlist("fayllar")
        if not fayllar:
            messages.error(request, "Fayl tanlanmadi.")
            return redirect("resp_yuklash")
        qol = _iso(request.POST.get("sana")) if len(fayllar) == 1 else None
        if request.POST.get("fon") == "1":
            return JsonResponse(_fonga_qosh(fayllar, request.user, qol))
        for f in fayllar:
            natijalar.append(_qabul(f, request.user, qol))
        soni = sum(1 for n in natijalar if n["ok"])
        if soni:
            messages.success(request, f"{soni} ta fayl o'qildi va saqlandi.")
    belgilar = {k.sana: k.ish for k in RespKun.objects.all()}
    sahifa = Paginator(RespYuklama.objects.select_related("yuklagan"), 30).get_page(request.GET.get("p"))
    for y in sahifa:
        y.kun_nomi = HAFTA[y.sana.weekday()]
        y.korinadi = R.ish_kuni_mi(y.sana, belgilar)
        y.kb = max(1, round(y.hajm / 1024))
        y.ogoh_soni = len(y.xabar.splitlines()) if y.xabar else 0
    return render(request, "core/resp_yuklash.html", {"natijalar": natijalar, "sahifa": sahifa})


# ---------------------------------------------------------------- orqa fonda o'qish (jonli holat)
ESKIRDI = datetime.timedelta(minutes=30)  # server qayta ishga tushsa, "jarayonda" qolib ketganlarni yopish uchun
KORSATISH = datetime.timedelta(hours=2)


def _ish_yangila(ish, **kw):
    for k, v_ in kw.items():
        setattr(ish, k, v_)
    ish.save(update_fields=list(kw))


def _fonga_qosh(fayllar, user, qol_sana):
    """Fayllarni tekshiradi, jarayon yozuvlarini yaratadi va orqa fonda o'qishni boshlaydi."""
    navbat = []
    for f in fayllar:
        ish = RespIsh.objects.create(fayl_nomi=f.name[:255], hajm=f.size, yuklagan=user)
        if not f.name.lower().endswith(".pdf"):
            _ish_yangila(ish, holat="xato", xabar="Faqat PDF fayl qabul qilinadi.", foiz=100, tugadi=timezone.now())
        elif f.size > MAX_HAJM:
            _ish_yangila(ish, holat="xato", xabar="Fayl juda katta (40 MB dan oshmasligi kerak).", foiz=100, tugadi=timezone.now())
        else:
            navbat.append((ish.id, f.read(), f.name, user.id, qol_sana))
    if navbat:
        _fon_boshlash(navbat)
    return {"ok": True, "soni": len(fayllar)}


def _fon_ishchi(navbat):
    try:
        for ish_id, data, nom, user_id, qol in navbat:
            ish = RespIsh.objects.get(pk=ish_id)
            try:
                _ish_yangila(ish, holat="jarayonda", bosqich="PDF ochilmoqda...", foiz=3)

                def jarayon(bosqich, foiz, ish=ish):
                    _ish_yangila(ish, bosqich=bosqich[:120], foiz=min(foiz, 99))

                out = _oqi_va_saqla(data, nom, User.objects.filter(pk=user_id).first(), qol, jarayon)
                if out["ok"]:
                    _ish_yangila(ish, holat="ogoh" if out["ogoh"] else "tayyor", bosqich="", foiz=100, sana=out["sana"], almashdi=out["almashdi"],
                                 xabar="\n".join(out["ogoh"][:40]), tugadi=timezone.now())
                else:
                    _ish_yangila(ish, holat="xato", bosqich="", foiz=100, sana=out["sana"], xabar=out["xabar"], tugadi=timezone.now())
            except Exception as e:  # noqa: BLE001
                _ish_yangila(ish, holat="xato", bosqich="", foiz=100, xabar=f"Kutilmagan xato: {e}"[:2000], tugadi=timezone.now())
    finally:
        connection.close()


def _fon_boshlash(navbat):
    t = threading.Thread(target=_fon_ishchi, args=(navbat,), daemon=True)
    t.start()
    return t


def _ish_dict(i):
    ogoh = i.xabar.splitlines() if i.holat == "ogoh" else []
    return {"id": i.id, "fayl": i.fayl_nomi, "hajm_kb": max(1, round(i.hajm / 1024)), "holat": i.holat, "holat_txt": i.get_holat_display(),
            "bosqich": i.bosqich, "foiz": i.foiz, "sana": _txt(i.sana) if i.sana else "", "almashdi": i.almashdi,
            "xabar": i.xabar if i.holat == "xato" else "", "ogoh": ogoh}


@ruxsat_kerak("resp_yuklash.korish")
def resp_yuklash_holat(request):
    """Oxirgi 2 soat ichidagi o'qish jarayonlari (sahifa jonli yangilanib turishi uchun)."""
    hozir = timezone.now()
    RespIsh.objects.filter(holat__in=("navbatda", "jarayonda"), vaqt__lt=hozir - ESKIRDI).update(
        holat="xato", xabar="Jarayon to'xtab qoldi (server qayta ishga tushgan bo'lishi mumkin). Faylni qayta yuklang.", bosqich="", foiz=100, tugadi=hozir)
    ishlar = list(RespIsh.objects.filter(vaqt__gte=hozir - KORSATISH)[:20])
    return JsonResponse({"ishlar": [_ish_dict(i) for i in ishlar], "faol": any(i.holat in ("navbatda", "jarayonda") for i in ishlar)})


# ---------------------------------------------------------------- yuklangan fayllar (yuklash sahifasida ko'rsatiladi)
def _fayl_yoli(y):
    asos = Path(settings.UPLOAD_DIR).resolve()
    yol = (asos / y.yol).resolve()
    if asos not in yol.parents:
        raise Http404
    return yol


@ruxsat_kerak("resp_fayllar.yuklab")
def resp_fayl_yuklab(request, pk):
    y = get_object_or_404(RespYuklama, pk=pk)
    yol = _fayl_yoli(y)
    if not yol.exists():
        raise Http404("Fayl diskda topilmadi.")
    nom = y.fayl_nomi if y.fayl_nomi.lower().endswith(".pdf") else y.fayl_nomi + ".pdf"
    return FileResponse(open(yol, "rb"), as_attachment=True, filename=nom, content_type="application/pdf")


@ruxsat_kerak("resp_fayllar.ochirish")
@require_POST
def resp_fayl_ochirish(request, pk):
    y = get_object_or_404(RespYuklama, pk=pk)
    sana, faolmi = y.sana, y.faol
    try:
        yol = _fayl_yoli(y)
        if yol.exists():
            yol.unlink()
    except Http404:
        pass
    y.delete()
    if faolmi:  # shu sananing oldingi (almashtirilgan) versiyasi bo'lsa, u amaldagi bo'ladi
        oldingi = RespYuklama.objects.filter(sana=sana).order_by("-vaqt").first()
        if oldingi:
            oldingi.faol = True
            oldingi.save(update_fields=["faol"])
    messages.success(request, f"{_txt(sana)} sanasidagi fayl o'chirildi.")
    return redirect("resp_yuklash")
