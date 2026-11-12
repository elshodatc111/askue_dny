import datetime
import json
import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import TP, Brigada, Hodim, Kuzatuv, Profil, Tuman, Yuklama
from .permissions import (BARCHA, BOLIMLAR, FAQAT_ADMIN, ROL_STANDART, birinchi_sahifa, bor, is_admin, ruxsat_kerak,
                          ruxsatlar, standart, tuman_ids, tuman_ruxsati)
from .services import eksport, importer
from .services import stats as S
from .services.names import hodimlarni_ajrat


# ---------------------------------------------------------------- yordamchilar
def _sana_txt(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _sanalar_royxati():
    return [{"iso": d.isoformat(), "txt": _sana_txt(d)} for d in reversed(S.mavjud_sanalar())]


def _sana_juftligi(request, tur=None):
    """a (bazaviy) va b (joriy) sanalar. a ixtiyoriy: ?a= bo'sh bo'lsa solishtirilmaydi."""
    sanalar = S.mavjud_sanalar(tur) if tur else S.mavjud_sanalar()
    b = S.aniq_sana(request.GET.get("b"))
    if b not in sanalar:
        b = sanalar[-1] if sanalar else None
    if "a" in request.GET:
        a = S.aniq_sana(request.GET.get("a"))
    else:
        oldingilar = [x for x in sanalar if b and x < b]
        a = oldingilar[-1] if oldingilar else None
    return a, b, sanalar


def _tuman_tanlash(request):
    """Foydalanuvchi ruxsatiga mos tuman filtri. (ruxsat, tuman_id) qaytaradi."""
    ruxsat = tuman_ids(request.user)
    tid = request.GET.get("tuman")
    tid = int(tid) if tid and tid.isdigit() else None
    if ruxsat is not None:
        if len(ruxsat) == 1:
            tid = ruxsat[0]
        elif tid not in ruxsat:
            tid = None
    return ruxsat, tid


def _tumanlar(ruxsat):
    qs = Tuman.objects.all()
    if ruxsat is not None:
        qs = qs.filter(pk__in=ruxsat)
    return qs


def _presetlar(b, sanalar):
    """Tez tanlash: kecha, 7 kun oldin, oy boshi."""
    if not b:
      return []
    oldin = [x for x in sanalar if x < b]
    out = []
    if oldin:
        out.append(("Kecha bilan", oldin[-1]))
    hafta = [x for x in oldin if x <= b - datetime.timedelta(days=7)]
    if hafta:
        out.append(("7 kun oldin", hafta[-1]))
    oy = [x for x in sanalar if x.year == b.year and x.month == b.month and x < b]
    if oy:
        out.append(("Oy boshi", oy[0]))
    return [{"nom": n, "iso": d.isoformat(), "txt": _sana_txt(d)} for n, d in out]


# ---------------------------------------------------------------- bosh panel
@login_required
def bosh(request):
    if not bor(request.user, "bosh.korish"):
        url = birinchi_sahifa(request.user)
        if url and url != "bosh":
            return redirect(url)
        raise PermissionDenied
    ruxsat, tuman_id = _tuman_tanlash(request)
    a, b, sanalar = _sana_juftligi(request)
    ctx = {"sanalar": _sanalar_royxati(), "a": a, "b": b, "tuman_id": tuman_id, "tumanlar": _tumanlar(ruxsat), "bosh_bor": bool(b)}
    if not b:
        return render(request, "core/bosh.html", ctx)
    tuman = Tuman.objects.filter(pk=tuman_id).first() if tuman_id else None
    ctx["tuman"] = tuman

    # nomlar: tuman yoki brigadalar
    daraja = "brigada" if tuman_id else "tuman"
    if tuman_id:
        obj = [(br.id, br.nom) for br in Brigada.objects.filter(tuman_id=tuman_id).order_by("raqam")] + [(None, "Biriktirilmagan")]
    else:
        obj = [(t.id, t.korsat) for t in _tumanlar(ruxsat)]
    ctx["daraja_nom"] = "Brigadalar" if tuman_id else "Tumanlar"

    kartalar, grafik, jadval = [], {"nomlar": [n for _, n in obj]}, {}
    ma = {}
    for tur in S.TURLAR:
        cur = S.jamlama(tur, b if S.sana_bor(tur, b) else None, ruxsat, tuman_id)
        prev = S.jamlama(tur, a, ruxsat, tuman_id) if a and S.sana_bor(tur, a) else None
        tot = S.qosh(cur.values())
        ptot = S.qosh(prev.values()) if prev is not None else None
        asosiy = "offline" if tur in ("dcu", "gprs") else "jami"
        delta = (tot[asosiy] - ptot[asosiy]) if ptot is not None else None
        kartalar.append({
            "tur": tur, "nom": S.TUR_NOM[tur], "qiymat": tot[asosiy], "jami": tot["jami"], "online": tot["online"],
            "k3": tot["k3"], "k30": tot["k30"],
            "bor": S.sana_bor(tur, b), "delta": delta, "delta_txt": S.fmt(abs(delta)) if delta is not None else "",
            "foiz": round(tot["offline"] / tot["jami"] * 100, 1) if tur in ("dcu", "gprs") and tot["jami"] else None,
            "spark": [x[asosiy] for x in S.trend(tur, ruxsat, tuman_id, limit=20)],
        })
        yig = S._yigish(cur, daraja)
        ma[tur] = [yig.get(oid, {}) for oid, _ in obj]
        jadval[tur] = tot
        grafik["trend_" + tur] = S.trend(tur, ruxsat, tuman_id, limit=45)
    ctx["kartalar"] = kartalar
    ctx["k3_sana"] = S.k3_sana(b)
    ctx["k30_sana"] = b - datetime.timedelta(days=31)

    def q(tur, key):
        return [x.get(key, 0) for x in ma[tur]]

    grafik["nometer_k"] = {k: q("nometer", k) for k in ["k3", "k30"]}
    grafik["nometer_b"] = {k: q("nometer", k) for k in ["b1", "b2", "b3", "b4"]}
    grafik["dcu_off"] = q("dcu", "offline")
    grafik["gprs_off"] = q("gprs", "offline")
    grafik["direct"] = q("direct", "jami")
    grafik["donut_muddat"] = [{"name": S.BUCKET_NOM[k], "value": jadval["nometer"][k]} for k in ["b1", "b2", "b3", "b4"]]
    grafik["donut_turi"] = [{"name": "Aholi", "value": jadval["nometer"]["aholi"]}, {"name": "Ulgurji", "value": jadval["nometer"]["ulgurji"]}, {"name": "Balans", "value": jadval["nometer"]["balans"]}]
    grafik["off_muddat"] = {t: {k: jadval[t][k] for k in ["b0", "b1", "b2", "b3", "b4"]} for t in ("dcu", "gprs")}
    grafik["tur_nom"] = S.TUR_QISQA
    ctx["grafik"] = grafik

    # qisqa jadval
    qator = []
    for i, (oid, nom) in enumerate(obj):
        qator.append({
            "id": oid, "nom": nom,
            "dcu": ma["dcu"][i].get("k3", 0), "gprs": ma["gprs"][i].get("k30", 0),
            "nometer": ma["nometer"][i].get("jami", 0), "nometer3": ma["nometer"][i].get("k3", 0),
            "nometer3090": ma["nometer"][i].get("b3", 0), "nometer90": ma["nometer"][i].get("b4", 0),
            "direct": ma["direct"][i].get("jami", 0),
        })
    ctx["qator"] = [r for r in qator if r["id"] is not None or any([r["dcu"], r["gprs"], r["nometer"], r["direct"]])]
    jt = {k: sum(r[k] for r in ctx["qator"]) for k in ("dcu", "gprs", "nometer", "nometer3", "nometer3090", "nometer90", "direct")}
    ctx["qator_jami"] = jt
    return render(request, "core/bosh.html", ctx)


# ---------------------------------------------------------------- dinamika
@ruxsat_kerak("dinamika.korish")
def dinamika(request):
    ruxsat, tuman_id = _tuman_tanlash(request)
    sahifa = request.GET.get("sahifa")
    if sahifa not in S.SAHIFALAR:  # eski ?tur= havolalari uchun
        sahifa = "2" if request.GET.get("tur") in ("nometer", "direct") else "1"
    a, b, sanalar = _sana_juftligi(request)
    jadval = S.dinamika_sahifa(sahifa, a, b, ruxsat, tuman_id) if b else None
    fmt_ = request.GET.get("format")
    if fmt_ in ("pdf", "pdf4", "zip", "xlsx"):
        return _dinamika_toplam(request, "pdf4" if fmt_ == "pdf" else fmt_, a, b, ruxsat, tuman_id)
    params = request.GET.copy()
    params.pop("format", None)
    yoq = []
    if jadval:
        for t, ok in zip(jadval["turlar"], jadval["bor"]):
            if not ok:
                yoq.append(S.TUR_NOM[t])
    ctx = {
        "params": params.urlencode(), "sahifa": sahifa, "sahifalar": [(k, v[0]) for k, v in S.SAHIFALAR.items()], "sahifa_nom": S.SAHIFALAR[sahifa][0],
        "jadval": jadval, "yoq_turlar": yoq, "a": a, "b": b,
        "sanalar": _sanalar_royxati(), "tuman_id": tuman_id, "tuman": Tuman.objects.filter(pk=tuman_id).first(),
        "tumanlar": _tumanlar(ruxsat), "presetlar": _presetlar(b, sanalar),
        "sarlavha": eksport._sarlavha({"tuman": (Tuman.objects.filter(pk=tuman_id).first().korsat if tuman_id and Tuman.objects.filter(pk=tuman_id).exists() else ""), "tur": S.SAHIFA_NOM[sahifa]}),
    }
    return render(request, "core/dinamika.html", ctx)


def _dinamika_toplam(request, fmt_, a, b, ruxsat, tuman_id):
    """xlsx: ikkala jadval bitta Excel faylida (2 varaq). pdf4: ikkala jadval bitta PDF da (viloyat: tumanlar kesimida, tuman: brigadalar kesimida).
    zip: har bir tuman uchun brigadalar kesimidagi 4 ta dinamika alohida PDF, hammasi bitta ZIP da."""
    import io
    import re
    import zipfile

    from django.http import HttpResponse

    if not bor(request.user, "dinamika.eksport"):
        raise PermissionDenied
    if not b:
        raise Http404("Ma'lumot yo'q")

    def elementlar(tid, nom):
        out = []
        for k in S.SAHIFALAR:
            j = S.dinamika_sahifa(k, a, b, ruxsat, tid)
            out.append((j, {"tur_nom": S.SAHIFALAR[k][0], "a": a, "b": b, "tuman": nom, "tur": S.SAHIFA_NOM[k], "yuklangan": S.yuklangan_vaqt(S.SAHIFALAR[k][1], b)}))
        return out

    def toza(t):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", eksport._lotin(t)).strip("_") or "tuman"

    sana = b.strftime("%Y-%m-%d")
    if fmt_ == "xlsx":
        tuman_obj = Tuman.objects.filter(pk=tuman_id).first()
        nom = tuman_obj.korsat if tuman_obj else ""
        return eksport.kopchilik_xlsx(elementlar(tuman_id, nom), f"dinamika_{toza(nom) + '_' if nom else ''}{sana}.xlsx")
    if fmt_ == "pdf4":
        tuman_obj = Tuman.objects.filter(pk=tuman_id).first()
        nom = tuman_obj.korsat if tuman_obj else ""
        data = eksport.kopchilik_pdf(elementlar(tuman_id, nom))
        fayl = f"dinamika_4_{toza(nom) + '_' if nom else ''}{sana}.pdf"
        resp = HttpResponse(data, content_type="application/pdf")
    else:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for t in _tumanlar(ruxsat):
                z.writestr(f"{toza(t.korsat)}_dinamika_{sana}.pdf", eksport.kopchilik_pdf(elementlar(t.id, t.korsat)))
        fayl = f"dinamika_tumanlar_brigadalar_{sana}.zip"
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{fayl}"'
    return resp


# ---------------------------------------------------------------- nomma-nom ro'yxat
def _bucket_q(ust):
    if ust == "b0":
        return Q(kun__lte=1) | Q(kun__isnull=True)
    return {
        "b1": Q(kun__gte=2, kun__lte=7), "b2": Q(kun__gte=8, kun__lte=30),
        "b3": Q(kun__gte=31, kun__lte=90), "b4": Q(kun__gt=90),
        "k3": Q(kun__gte=S.K3_KUN), "k30": Q(kun__gte=31),
    }[ust]


def _royxat_qs(request, tur, sana, ruxsat, tuman_id):
    qs = Kuzatuv.objects.filter(yuklama__tur=tur, yuklama__sana=sana, yuklama__holat="tayyor")
    if ruxsat is not None:
        qs = qs.filter(tp__tuman_id__in=ruxsat)
    if tuman_id:
        qs = qs.filter(tp__tuman_id=tuman_id)
    br = request.GET.get("brigada", "")
    if br == "yoq":
        qs = qs.filter(tp__brigada__isnull=True)
    elif br.isdigit():
        qs = qs.filter(tp__brigada_id=int(br))
    ust = request.GET.get("ust", "")
    if ust in ("b0", "b1", "b2", "b3", "b4", "k3", "k30"):
        qs = qs.filter(_bucket_q(ust))
    elif ust in ("aholi", "ulgurji", "balans"):
        qs = qs.filter(abonent_turi=ust)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(raqam__icontains=q) | Q(abonent__icontains=q) | Q(hisob__icontains=q) | Q(tp__raqam__icontains=q) | Q(manzil__icontains=q) | Q(tp__feeder__icontains=q) | Q(tp__podstansiya__icontains=q))
    return qs


@ruxsat_kerak("royxat.korish")
def royxat(request):
    ruxsat, tuman_id = _tuman_tanlash(request)
    tur = request.GET.get("tur", "nometer")
    if tur not in S.TURLAR:
        tur = "nometer"
    a, b, sanalar = _sana_juftligi(request, tur)
    holat = request.GET.get("holat", "")
    qs = None
    if b:
        if holat == "tuzalgan" and a:
            # A kunda bor, B kunda yo'q
            b_raqam = set(Kuzatuv.objects.filter(yuklama__tur=tur, yuklama__sana=b, yuklama__holat="tayyor").values_list("raqam", flat=True))
            qs = _royxat_qs(request, tur, a, ruxsat, tuman_id).exclude(raqam__in=b_raqam) if len(b_raqam) < 60000 else None
        else:
            qs = _royxat_qs(request, tur, b, ruxsat, tuman_id)
            if holat == "yangi" and a:
                a_raqam = set(Kuzatuv.objects.filter(yuklama__tur=tur, yuklama__sana=a, yuklama__holat="tayyor").values_list("raqam", flat=True))
                qs = qs.exclude(raqam__in=a_raqam)
        qs = qs.select_related("tp", "tp__tuman", "tp__brigada").order_by("-kun", "tp__tuman__tartib", "id") if qs is not None else None
    if request.GET.get("format") == "xlsx" and qs is not None:
        if not bor(request.user, "royxat.eksport"):
            raise PermissionDenied
        return _eksport(qs, tur)
    sahifa = Paginator(qs, 100).get_page(request.GET.get("page")) if qs is not None else None
    params = request.GET.copy()
    params.pop("page", None)
    brigadalar = Brigada.objects.filter(tuman_id=tuman_id).order_by("raqam") if tuman_id else []
    sarlavha = S.TUR_NOM[tur]
    ust = request.GET.get("ust", "")
    nom_ust = dict((k, n) for k, n, _ in S.USTUNLAR[tur]).get(ust, "")
    ctx = {
        "tur": tur, "turlar": [(t, S.TUR_NOM[t]) for t in S.TURLAR], "sahifa": sahifa, "a": a, "b": b,
        "sanalar": _sanalar_royxati(), "tuman_id": tuman_id, "tumanlar": _tumanlar(ruxsat), "brigadalar": brigadalar,
        "brigada": request.GET.get("brigada", ""), "q": request.GET.get("q", ""), "ust": ust, "nom_ust": nom_ust,
        "holat": holat, "params": params.urlencode(), "sarlavha": sarlavha,
        "jami_soni": sahifa.paginator.count if sahifa else 0,
    }
    return render(request, "core/royxat.html", ctx)


def _eksport(qs, tur):
    import openpyxl

    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("Ro'yxat")
    if tur in ("dcu", "gprs"):
        ws.append(["Tuman", "Podstansiya", "Feeder", "TP", "Brigada", "Qurilma raqami", "Oxirgi aloqa", "Necha kun", "Operator", "IP", "Kenglik", "Uzunlik"])
    else:
        ws.append(["Tuman", "Podstansiya", "Feeder", "TP", "Brigada", "Hisoblagich raqami", "Hisob raqami", "Abonent", "Abonent turi", "Aloqa turi", "Necha kun", "Manzil", "Kenglik", "Uzunlik"])
    for i, k in enumerate(qs.iterator(chunk_size=2000)):
        if i >= 150000:
            break
        base = [k.tp.tuman.korsat, k.tp.podstansiya, k.tp.feeder, k.tp.raqam, k.tp.brigada.nom if k.tp.brigada else "Biriktirilmagan"]
        if tur in ("dcu", "gprs"):
            ws.append(base + [k.raqam, k.vaqt.strftime("%d.%m.%Y %H:%M") if k.vaqt else "", k.kun, k.operator, k.ip, k.lat, k.lon])
        else:
            ws.append(base + [k.raqam, k.hisob, k.abonent, k.abonent_turi, k.aloqa_turi, k.kun, k.manzil, k.lat, k.lon])
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{tur}_royxat.xlsx"'
    wb.save(resp)
    return resp


# ---------------------------------------------------------------- xarita
XARITA_TURLAR = [("all", "Barchasi")] + [(t, S.TUR_NOM[t]) for t in S.TURLAR]
XARITA_LIMIT = 7000  # bitta tur uchun brauzerga yuboriladigan eng ko'p nuqta


@ruxsat_kerak("xarita.korish")
def xarita(request):
    ruxsat, tuman_id = _tuman_tanlash(request)
    tur = request.GET.get("tur", "all")
    if tur not in dict(XARITA_TURLAR):
        tur = "all"
    a, b, sanalar = _sana_juftligi(request, None if tur == "all" else tur)
    ctx = {
        "tur": tur, "turlar": XARITA_TURLAR, "b": b, "sanalar": _sanalar_royxati(),
        "tuman_id": tuman_id, "tumanlar": _tumanlar(ruxsat), "ust": request.GET.get("ust", ""),
        "brigadalar": Brigada.objects.filter(tuman_id=tuman_id).order_by("raqam") if tuman_id else [],
        "brigada": request.GET.get("brigada", ""),
    }
    return render(request, "core/xarita.html", ctx)


@ruxsat_kerak("xarita.korish")
def xarita_api(request):
    """Xarita nuqtalari. Har bir nuqta: [lat, lon, tur, raqam, kun, tuman, feeder, tp, abonent, hisob, abonent_turi, manzil, oxirgi_aloqa, aloqa_turi]"""
    from django.db.models import F

    ruxsat, tuman_id = _tuman_tanlash(request)
    tur = request.GET.get("tur", "all")
    turlar = list(S.TURLAR) if tur == "all" else ([tur] if tur in S.TURLAR else [])
    b0 = S.aniq_sana(request.GET.get("b"))
    nuq, hisob = [], {}
    for t in turlar:
        sanalar = S.mavjud_sanalar(t)
        b = b0 if b0 in sanalar else (sanalar[-1] if sanalar else None)
        if not b:
            hisob[t] = 0
            continue
        qs = _royxat_qs(request, t, b, ruxsat, tuman_id).filter(lat__isnull=False, lon__isnull=False)
        jami = qs.count()
        hisob[t] = jami
        if jami > XARITA_LIMIT:  # tekis tanlab olish
            qs = qs.annotate(_m=F("id") % (jami // XARITA_LIMIT + 1)).filter(_m=0)
        qs = qs.select_related("tp", "tp__tuman")[: XARITA_LIMIT + 500]
        for k in qs:
            nuq.append([
                k.lat, k.lon, t, k.raqam, k.kun if k.kun is not None else -1, k.tp.tuman.korsat, k.tp.feeder, k.tp.raqam,
                k.abonent, k.hisob, k.abonent_turi, k.manzil, k.vaqt.strftime("%d.%m.%Y %H:%M") if k.vaqt else "", k.aloqa_turi,
            ])
    return JsonResponse({"nuqtalar": nuq, "hisob": hisob, "jami": sum(hisob.values())})


OYLAR = {1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun", 7: "iyul", 8: "avgust", 9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"}


# ---------------------------------------------------------------- yuklash (admin)
@ruxsat_kerak("yuklash.korish")
def yuklash(request):
    if request.method == "POST":
        if not bor(request.user, "yuklash.yuklash"):
            raise PermissionDenied
        fayllar = request.FILES.getlist("fayllar")
        if not fayllar:
            messages.error(request, "Fayl tanlanmadi.")
            return redirect("yuklash")
        forma_sana = S.aniq_sana(request.POST.get("sana"))
        fayldan = request.POST.get("fayldan") == "1"
        majburiy = request.POST.get("tur") or None
        if majburiy not in ("area", "dcu", "gprs", "nometer", "direct"):
            majburiy = None
        if majburiy and len(fayllar) > 1:
            majburiy = None
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        ishlar = []
        for f in fayllar:
            yol = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}.xlsx")
            with open(yol, "wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)
            try:
                info = importer.aniqlash(yol, f.name, majburiy)
            except Exception as e:  # noqa
                messages.error(request, f"{f.name}: {e}")
                os.remove(yol)
                continue
            sana = (info["sana"] if fayldan and info["sana"] else None) or forma_sana or datetime.date.today()
            y = Yuklama.objects.create(tur=info["tur"], sana=sana, fayl_nomi=f.name[:255], yuklagan=request.user, holat="jarayonda", xabar="Navbatda...")
            ishlar.append({"yuklama_id": y.id, "path": yol, "header": info["header"], "tur": info["tur"]})
            messages.info(request, f"{f.name}: {y.get_tur_display()}, sana {_sana_txt(sana)}. Qayta ishlanmoqda...")
        if ishlar:
            importer.fonda_boshlash(ishlar)
        return redirect("yuklash")
    royxat = Yuklama.objects.select_related("yuklagan").order_by("-vaqt")[:40]
    return render(request, "core/yuklash.html", {"royxat": royxat, "bugun": datetime.date.today(), "turlar": Yuklama.TURLAR})


@ruxsat_kerak("yuklash.korish")
def yuklash_holat(request):
    out = []
    for y in Yuklama.objects.order_by("-vaqt")[:40]:
        out.append({"id": y.id, "holat": y.holat, "holat_txt": y.get_holat_display(), "xabar": y.xabar[:300], "qatorlar": y.qatorlar})
    return JsonResponse({"royxat": out, "jarayonda": any(x["holat"] == "jarayonda" for x in out)})


@ruxsat_kerak("yuklash.ochirish")
@require_POST
def yuklama_ochirish(request, pk):
    y = get_object_or_404(Yuklama, pk=pk)
    y.delete()
    messages.success(request, "Yuklama o'chirildi.")
    return redirect("yuklash")


# ---------------------------------------------------------------- brigadalar
def _ruxsatli_tumanlar(user):
    qs = Tuman.objects.all()
    ids = tuman_ids(user)
    return qs if ids is None else qs.filter(pk__in=ids)


def _tuman_tekshir(request, tuman_id):
    if not tuman_ruxsati(request.user, tuman_id):
        raise PermissionDenied


@ruxsat_kerak("brigadalar.korish")
def brigadalar(request):
    tumanlar = _ruxsatli_tumanlar(request.user)
    tid = request.GET.get("tuman")
    tuman = tumanlar.filter(pk=tid).first() if tid and tid.isdigit() else tumanlar.first()
    royxat = []
    if tuman:
        for br in Brigada.objects.filter(tuman=tuman).prefetch_related("hodimlar").annotate(tp_soni=Count("tplar")).order_by("raqam"):
            royxat.append(br)
    yoq = TP.objects.filter(tuman=tuman, brigada__isnull=True).count() if tuman else 0
    return render(request, "core/brigadalar.html", {"tumanlar": tumanlar, "tuman": tuman, "royxat": royxat, "yoq": yoq})


@ruxsat_kerak("brigadalar.yaratish")
@require_POST
def brigada_yangi(request, tuman_id):
    t = get_object_or_404(Tuman, pk=tuman_id)
    _tuman_tekshir(request, t.id)
    raqam = (Brigada.objects.filter(tuman=t).order_by("-raqam").values_list("raqam", flat=True).first() or 0) + 1
    b = Brigada.objects.create(tuman=t, raqam=raqam, nom=f"Brigada {raqam}")
    messages.success(request, "Yangi brigada yaratildi.")
    if bor(request.user, "brigadalar.tahrirlash"):
        return redirect("brigada_tahrir", pk=b.id)
    return redirect(f"/brigadalar/?tuman={t.id}")


@ruxsat_kerak("brigadalar.tahrirlash")
def brigada_tahrir(request, pk):
    b = get_object_or_404(Brigada.objects.select_related("tuman"), pk=pk)
    _tuman_tekshir(request, b.tuman_id)
    if request.method == "POST":
        b.nom = (request.POST.get("nom") or b.nom).strip()[:120]
        try:
            b.raqam = int(request.POST.get("raqam") or b.raqam)
        except ValueError:
            pass
        b.telefon = (request.POST.get("telefon") or "").strip()[:200]
        b.save()
        b.hodimlar.all().delete()
        for qator in (request.POST.get("hodimlar") or "").splitlines():
            p = [x.strip() for x in qator.split(";")]
            if p and p[0]:
                Hodim.objects.create(brigada=b, ism=p[0][:200], pinfl=(p[1] if len(p) > 1 else "")[:20], telefon=(p[2] if len(p) > 2 else "")[:40])
        messages.success(request, "Brigada saqlandi.")
        return redirect(f"/brigadalar/?tuman={b.tuman_id}")
    matn = "\n".join("; ".join(x for x in [h.ism, h.pinfl, h.telefon] if x or True).rstrip("; ") for h in b.hodimlar.all())
    boshqalar = Brigada.objects.filter(tuman=b.tuman).exclude(pk=b.pk).order_by("raqam")
    return render(request, "core/brigada_tahrir.html", {"b": b, "matn": matn, "boshqalar": boshqalar, "tp_soni": b.tplar.count()})


@ruxsat_kerak("brigadalar.ochirish")
@require_POST
def brigada_ochirish(request, pk):
    b = get_object_or_404(Brigada, pk=pk)
    _tuman_tekshir(request, b.tuman_id)
    tid = b.tuman_id
    maqsad = request.POST.get("maqsad")
    if maqsad and maqsad.isdigit():
        TP.objects.filter(brigada=b).update(brigada_id=int(maqsad))
        messages.success(request, "TP lar boshqa brigadaga ko'chirildi va brigada o'chirildi.")
    else:
        messages.success(request, "Brigada o'chirildi (TP lar biriktirilmagan holatga o'tdi).")
    b.delete()
    return redirect(f"/brigadalar/?tuman={tid}")


@ruxsat_kerak("tp_kochirish.korish")
def tp_kochirish(request):
    tumanlar = _ruxsatli_tumanlar(request.user)
    tid = request.GET.get("tuman") or request.POST.get("tuman")
    tuman = tumanlar.filter(pk=tid).first() if tid and str(tid).isdigit() else tumanlar.first()
    if request.method == "POST" and tuman:
        if not bor(request.user, "tp_kochirish.kochirish"):
            raise PermissionDenied
        ids = [int(x) for x in request.POST.getlist("tp") if x.isdigit()]
        maqsad = request.POST.get("maqsad")
        if ids and maqsad:
            bid = None if maqsad == "yoq" else int(maqsad)
            if bid and not Brigada.objects.filter(pk=bid, tuman=tuman).exists():
                raise PermissionDenied
            soni = TP.objects.filter(pk__in=ids, tuman=tuman).update(brigada_id=bid)
            messages.success(request, f"{soni} ta TP ko'chirildi.")
        else:
            messages.error(request, "TP va maqsad brigadani tanlang.")
        return redirect(f"/tp-kochirish/?tuman={tuman.id}&manba={request.POST.get('manba', '')}&q={request.POST.get('q', '')}")
    manba = request.GET.get("manba", "")
    q = (request.GET.get("q") or "").strip()
    qs = TP.objects.filter(tuman=tuman).select_related("brigada") if tuman else TP.objects.none()
    if manba == "yoq":
        qs = qs.filter(brigada__isnull=True)
    elif manba.isdigit():
        qs = qs.filter(brigada_id=int(manba))
    if q:
        qs = qs.filter(Q(raqam__icontains=q) | Q(feeder__icontains=q) | Q(podstansiya__icontains=q))
    jami = qs.count()
    brigadalar_ = Brigada.objects.filter(tuman=tuman).order_by("raqam") if tuman else []
    return render(request, "core/tp_kochirish.html", {
        "tumanlar": tumanlar, "tuman": tuman, "tplar": qs.order_by("podstansiya", "feeder", "raqam")[:500], "jami": jami,
        "brigadalar": brigadalar_, "manba": manba, "q": q,
    })


# ---------------------------------------------------------------- foydalanuvchilar (faqat administrator)
def _matritsa(tanlangan, admin_rol=False):
    """Ruxsatlar jadvali uchun: bo'limlar va ularning amaliyotlari (belgilangan holati bilan)."""
    out = []
    for kod, nom, amallar, faqat_admin in BOLIMLAR:
        out.append({
            "kod": kod, "nom": nom, "faqat_admin": faqat_admin,
            "amallar": [{"kod": f"{kod}.{a}", "nom": an, "on": admin_rol or f"{kod}.{a}" in tanlangan} for a, an in amallar],
        })
    return out


def _ruxsat_soni(u):
    pr = getattr(u, "profil", None)
    return len(ruxsatlar(u)), len(BARCHA), bool(pr and pr.ruxsatlar)


@ruxsat_kerak("foydalanuvchilar.korish")
def foydalanuvchilar(request):
    royxat = list(User.objects.select_related("profil", "profil__tuman").order_by("username"))
    for u in royxat:
        u.rx_soni, u.rx_jami, u.rx_ozgargan = _ruxsat_soni(u)
    return render(request, "core/foydalanuvchilar.html", {"royxat": royxat})


@ruxsat_kerak("foydalanuvchilar.korish")
def foydalanuvchi_tahrir(request, pk=None):
    u = get_object_or_404(User, pk=pk) if pk else None
    if u and not bor(request.user, "foydalanuvchilar.tahrirlash"):
        raise PermissionDenied
    if not u and not bor(request.user, "foydalanuvchilar.yaratish"):
        raise PermissionDenied
    xato = None
    tanlangan = set()
    if request.method == "POST":
        p = request.POST
        username = (p.get("username") or "").strip()
        rol = p.get("rol") or "tuman_hodim"
        if rol not in dict(Profil.ROLLAR):
            rol = "tuman_hodim"
        tuman_id = p.get("tuman") or None
        parol = p.get("parol") or ""
        tanlangan = {k for k in p.getlist("rx") if k in BARCHA and k not in FAQAT_ADMIN}
        tanlangan = {k for k in tanlangan if k.endswith(".korish") or k.split(".")[0] + ".korish" in tanlangan}
        if not username:
            xato = "Login kiritilmadi."
        elif User.objects.filter(username=username).exclude(pk=u.pk if u else None).exists():
            xato = "Bunday login mavjud."
        elif not u and len(parol) < 6:
            xato = "Parol kamida 6 ta belgi bo'lishi kerak."
        elif rol == "tuman_hodim" and not tuman_id:
            xato = "Tuman hodimi uchun tuman tanlanishi shart."
        elif u and u.pk == request.user.pk and (rol != "admin" and not u.is_superuser):
            xato = "O'zingizning administrator rolingizni olib tashlab bo'lmaydi."
        if not xato:
            if not u:
                u = User(username=username)
            u.username = username
            u.first_name = (p.get("ism") or "")[:150]
            u.is_active = p.get("faol") == "1"
            if parol:
                u.set_password(parol)
            u.save()
            pr = Profil.objects.get_or_create(user=u)[0]
            pr.rol = rol
            pr.tuman_id = int(tuman_id) if tuman_id else None
            pr.telefon = (p.get("telefon") or "")[:40]
            if rol == "admin":
                pr.ruxsatlar = {}
            else:
                std = standart(rol)
                ozgargan = {}
                for k in BARCHA:
                    if k in FAQAT_ADMIN:
                        continue
                    if (k in tanlangan) != (k in std):
                        ozgargan[k] = k in tanlangan
                pr.ruxsatlar = ozgargan
            pr.save()
            messages.success(request, "Foydalanuvchi saqlandi.")
            return redirect("foydalanuvchilar")
        admin_rol = rol == "admin"
    else:
        if u:
            tanlangan = set(ruxsatlar(u))
            admin_rol = is_admin(u)
        else:
            tanlangan = standart("tuman_hodim")
            admin_rol = False
    standartlar = {rol: sorted(k for k in v if k not in FAQAT_ADMIN) for rol, v in ROL_STANDART.items()}
    return render(request, "core/foydalanuvchi_tahrir.html", {
        "u": u, "xato": xato, "rollar": Profil.ROLLAR, "tumanlar": Tuman.objects.all(),
        "p": request.POST if request.method == "POST" else None,
        "matritsa": _matritsa(tanlangan, admin_rol), "standartlar": standartlar,
    })
