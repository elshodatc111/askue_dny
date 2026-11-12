"""Statistika: jamlama, dinamika jadvali (sanalarni solishtirish), trend."""
import datetime
from collections import defaultdict

from django.db.models import Sum

from ..models import Brigada, Tuman, TPSana, Yuklama

BUCKETS = ["b0", "b1", "b2", "b3", "b4"]
BUCKET_NOM = {"b0": "1 kungacha", "b1": "2-7 kun", "b2": "7-30 kun", "b3": "30-90 kun", "b4": "90 kundan ortiq"}
SUM_FIELDS = ["jami", "online"] + BUCKETS + ["aholi", "ulgurji", "balans"]
# hisoblab chiqariladigan maydonlar: offline = b0..b4; k3 = 3 kundan ortiq (oxirgi aloqa ma'lumot sanasidan 2 kun va undan
# oldin, masalan 12.11 da -> 10.11 va undan oldin); k30 = 30 kundan ortiq (b3 + b4)
HISOB_FIELDS = ["offline", "k3", "k30"]
K3_KUN = 2


def hisobla(d):
    d["offline"] = sum(d[b] for b in BUCKETS)
    d["k3"] = d["offline"] - d["b0"]
    d["k30"] = d["b3"] + d["b4"]
    return d


def k3_sana(b):
    return b - datetime.timedelta(days=K3_KUN) if b else None

TUR_NOM = {
    "dcu": "Konsentratorlar",
    "gprs": "GPRS hisoblagichlar",
    "nometer": "Aloqadan chiqib ketgan hisoblagichlar",
    "direct": "To'g'ridan-to'g'ri ulanish (Primichka)",
}
TUR_QISQA = {"dcu": "Konsentrator", "gprs": "GPRS hisoblagich", "nometer": "Aloqadan chiqqan", "direct": "To'g'ridan-to'g'ri ulanish (Primichka)"}
TURLAR = ["dcu", "gprs", "nometer", "direct"]
# dinamika sahifalari: har birida ikkita jadval
SAHIFALAR = {"1": ("Konsentrator va GPRS", ["dcu", "gprs"]), "2": ("Aloqadan chiqib ketgan va Primichka", ["nometer", "direct"])}

# (kalit, sarlavha, ma'no: n=neytral, g=ko'payishi yaxshi, b=ko'payishi yomon)
_OFF = [("offline", "Offline jami", "b"), ("k3", "3 kundan ortiq", "b"), ("k30", "30 kundan ortiq", "b")]
USTUNLAR = {
    "dcu": [("jami", "Jami", "n"), ("online", "Online", "g")] + _OFF,
    "gprs": [("jami", "Jami", "n"), ("online", "Online", "g")] + _OFF,
    "nometer": [("jami", "Jami", "b"), ("aholi", "Aholi", "b"), ("ulgurji", "Ulgurji", "b"), ("balans", "Balans", "b")]
    + [(b, BUCKET_NOM[b], "b") for b in ["b1", "b2", "b3", "b4"]],
    "direct": [("jami", "Jami", "b"), ("aholi", "Aholi", "b"), ("ulgurji", "Ulgurji", "b")],
}
# eksport (Excel/PDF) uchun sarlavha guruhlari: (guruh nomi, [ustun kalitlari]) - kalitlar ketma-ket joylashgan
GURUHLAR = {
    "dcu": [("Konsentratorlar", ["jami", "online", "offline", "k3", "k30"])],
    "gprs": [("GPRS hisoblagichlar", ["jami", "online", "offline", "k3", "k30"])],
    "nometer": [("Aloqadan chiqib ketgan hisoblagichlar", ["jami"]),
                ("Abonent turi bo'yicha", ["aholi", "ulgurji", "balans"]),
                ("Aloqadan chiqib ketgan muddati bo'yicha soni", ["b1", "b2", "b3", "b4"])],
    "direct": [("To'g'ridan-to'g'ri ulanishlar (Primichka)", ["jami", "aholi", "ulgurji"])],
}
# eksport sarlavhasi: "Qashqadaryo HETK hududida CAS dasturida ..."
EKSPORT_SARLAVHA = {
    "dcu": "CAS dasturida mavjud konsentratorlar holati bo'yicha",
    "gprs": "CAS dasturida mavjud GPRS hisoblagichlar holati bo'yicha",
    "nometer": "CAS dasturida aloqadan chiqib ketgan hisoblagichlar bo'yicha",
    "direct": "CAS dasturida to'g'ridan-to'g'ri ulanishlar (Primichka) bo'yicha",
}
# nomma-nom ro'yxat ochish mumkin bo'lgan ustunlar
BOSILADI = {
    "dcu": {"offline", "k3", "k30", "b0", "b1", "b2", "b3", "b4"},
    "gprs": {"offline", "k3", "k30", "b0", "b1", "b2", "b3", "b4"},
    "nometer": {"jami", "k3", "k30", "aholi", "ulgurji", "balans", "b1", "b2", "b3", "b4"},
    "direct": {"jami", "aholi", "ulgurji"},
}


def fmt(n):
    if n is None:
        return "-"
    return f"{n:,}".replace(",", " ")


def mavjud_sanalar(tur=None):
    qs = Yuklama.objects.filter(holat="tayyor").exclude(tur="area")
    if tur:
        qs = qs.filter(tur=tur)
    return sorted(set(qs.values_list("sana", flat=True)))


def sana_bor(tur, sana):
    return bool(sana) and Yuklama.objects.filter(tur=tur, sana=sana, holat="tayyor").exists()


def yuklangan_vaqt(turlar, sana):
    """Berilgan sana uchun shu turlarning eng oxirgi yuklangan vaqti (mahalliy)."""
    from django.db.models import Max

    return Yuklama.objects.filter(tur__in=turlar, sana=sana, holat="tayyor").aggregate(m=Max("vaqt"))["m"] if sana else None


def aniq_sana(s):
    if isinstance(s, datetime.date):
        return s
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def jamlama(tur, sana, ruxsat=None, tuman_id=None):
    """{(tuman_id, brigada_id): {maydon: qiymat}}"""
    if not sana:
        return {}
    qs = TPSana.objects.filter(yuklama__tur=tur, yuklama__sana=sana, yuklama__holat="tayyor")
    if ruxsat is not None:
        qs = qs.filter(tp__tuman_id__in=ruxsat)
    if tuman_id:
        qs = qs.filter(tp__tuman_id=tuman_id)
    rows = qs.values("tp__tuman_id", "tp__brigada_id").annotate(**{"s_" + f: Sum(f) for f in SUM_FIELDS})
    out = {}
    for r in rows:
        d = hisobla({f: r["s_" + f] or 0 for f in SUM_FIELDS})
        k = (r["tp__tuman_id"], r["tp__brigada_id"])
        if k in out:
            for f in d:
                out[k][f] += d[f]
        else:
            out[k] = d
    return out


def qosh(items):
    t = {f: 0 for f in SUM_FIELDS + HISOB_FIELDS}
    for d in items:
        for f in t:
            t[f] += d.get(f, 0)
    return t


def _yigish(data, daraja):
    """daraja='tuman' -> {tuman_id: d}; 'brigada' -> {brigada_id|None: d}"""
    g = defaultdict(list)
    for (tid, bid), d in data.items():
        g[tid if daraja == "tuman" else bid].append(d)
    return {k: qosh(v) for k, v in g.items()}


def _katak(ust, b, a, bor_b, bor_a):
    key, ma = ust[0], ust[2]
    v = b.get(key, 0) if (b is not None and bor_b) else None
    d = None
    if v is not None and bor_a and a is not None:
        d = v - a.get(key, 0)
    if d is None or d == 0:
        cls = "nol" if d == 0 else ""
        belgi = ""
    else:
        yomon = (d > 0 and ma == "b") or (d < 0 and ma == "g")
        yaxshi = (d < 0 and ma == "b") or (d > 0 and ma == "g")
        cls = "yomon" if yomon else "yaxshi" if yaxshi else "neytral"
        belgi = f"{'↑' if d > 0 else '↓'} {fmt(abs(d))}"
    return {"key": key, "v": v, "vt": fmt(v), "d": d, "dt": belgi, "cls": cls}


def hodimlar_matni(brigada):
    return [h.ism for h in brigada.hodimlar.all()]


def _hint(key, sana_b):
    """Ustun sarlavhasi tagidagi izoh (sanalar bilan)."""
    if not sana_b:
        return ""
    if key == "k3":
        return f"{k3_sana(sana_b):%d.%m} va undan oldin"
    if key == "k30":
        return f"{sana_b - datetime.timedelta(days=31):%d.%m} va undan oldin"
    return ""


def dinamika(tur, sana_a, sana_b, ruxsat, tuman_id=None):
    """Dinamika jadvali: tumanlar (yoki tanlangan tuman brigadalari) bo'yicha."""
    ust = [u + (_hint(u[0], sana_b),) for u in USTUNLAR[tur]]
    bor_b = sana_bor(tur, sana_b)
    bor_a = sana_bor(tur, sana_a)
    B = jamlama(tur, sana_b, ruxsat, tuman_id) if bor_b else {}
    A = jamlama(tur, sana_a, ruxsat, tuman_id) if bor_a else {}
    qator = []
    if tuman_id:
        tuman = Tuman.objects.get(pk=tuman_id)
        bb, aa = _yigish(B, "brigada"), _yigish(A, "brigada")
        for br in Brigada.objects.filter(tuman_id=tuman_id).prefetch_related("hodimlar").order_by("raqam"):
            qator.append({
                "id": br.id, "nom": br.nom, "hodimlar": hodimlar_matni(br), "tur": "brigada", "tuman_id": tuman_id,
                "katak": [_katak(u, bb.get(br.id), aa.get(br.id), bor_b, bor_a) for u in ust],
            })
        if None in bb or None in aa:
            qator.append({
                "id": "yoq", "nom": "Biriktirilmagan", "hodimlar": [], "tur": "yoq", "tuman_id": tuman_id,
                "katak": [_katak(u, bb.get(None), aa.get(None), bor_b, bor_a) for u in ust],
            })
        jb, ja = qosh(bb.values()), qosh(aa.values())
        nom = tuman.korsat
    else:
        bb, aa = _yigish(B, "tuman"), _yigish(A, "tuman")
        tq = Tuman.objects.all()
        if ruxsat is not None:
            tq = tq.filter(pk__in=ruxsat)
        for t in tq:
            qator.append({
                "id": t.id, "nom": t.korsat, "hodimlar": [], "tur": "tuman", "tuman_id": t.id,
                "katak": [_katak(u, bb.get(t.id), aa.get(t.id), bor_b, bor_a) for u in ust],
            })
        jb, ja = qosh(bb.values()), qosh(aa.values())
        nom = "Qashqadaryo HETK" if ruxsat is None else "Jami"
    jami = {"nom": nom, "katak": [_katak(u, jb, ja, bor_b, bor_a) for u in ust]}
    return {"ustunlar": ust, "qatorlar": qator, "jami": jami, "bor_b": bor_b, "bor_a": bor_a, "bosiladi": BOSILADI[tur],
            "guruhlar": GURUHLAR[tur]}


SAHIFA_NOM = {"1": "p1", "2": "p2"}
EKSPORT_SARLAVHA["p1"] = "CAS dasturida mavjud konsentratorlar va GPRS hisoblagichlar holati bo'yicha"
EKSPORT_SARLAVHA["p2"] = "CAS dasturida aloqadan chiqib ketgan hisoblagichlar va to'g'ridan-to'g'ri ulanishlar (Primichka) bo'yicha"


def dinamika_sahifa(sahifa, sana_a, sana_b, ruxsat, tuman_id=None):
    """Sahifadagi ikki turni bitta jadvalga birlashtiradi: bir xil qatorlar, ustunlar guruhlari yonma-yon."""
    turlar = SAHIFALAR[sahifa][1]
    js = [dinamika(t, sana_a, sana_b, ruxsat, tuman_id) for t in turlar]
    ustunlar, guruhlar, guruh_idx = [], [], []
    for t, j in zip(turlar, js):
        b0 = len(ustunlar)
        ustunlar += [u + (t, bool(b0) and n == 0) for n, u in enumerate(j["ustunlar"])]
        guruhlar.append((TUR_NOM[t], len(j["ustunlar"]), t))
        guruh_idx.append((TUR_NOM[t], list(range(b0, len(ustunlar)))))

    def birlash(qatorlar):
        katak = []
        for gi, (t, q) in enumerate(zip(turlar, qatorlar)):
            for n, c in enumerate(q["katak"]):
                katak.append(dict(c, tur=t, bos=c["key"] in BOSILADI[t], gs=bool(gi) and n == 0))
        return katak

    # qatorlarni id bo'yicha birlashtirish (ba'zi turda "Biriktirilmagan" qatori bo'lmasligi mumkin)
    tartib, xarita = [], []
    for j_ in js:
        d = {}
        for r in j_["qatorlar"]:
            d[r["id"]] = r
            if r["id"] not in tartib:
                tartib.append(r["id"])
        xarita.append(d)
    bosh = {"v": None, "vt": "-", "d": None, "dt": "", "cls": ""}
    qator = []
    for rid in tartib:
        asos = next(d[rid] for d in xarita if rid in d)
        q_ = [d.get(rid) or {"katak": [dict(bosh, key=u[0]) for u in j_["ustunlar"]]} for d, j_ in zip(xarita, js)]
        r2 = dict(asos)
        r2["katak"] = birlash(q_)
        qator.append(r2)
    jami = {"nom": js[0]["jami"]["nom"], "katak": birlash([j["jami"] for j in js])}
    return {"ustunlar": ustunlar, "qatorlar": qator, "jami": jami, "bor": [j["bor_b"] for j in js], "bor_a": [j["bor_a"] for j in js],
            "turlar": turlar, "guruhlar_veb": guruhlar, "guruh_idx": guruh_idx, "birlashgan": True}


def trend(tur, ruxsat, tuman_id=None, brigada_id=None, limit=45):
    qs = TPSana.objects.filter(yuklama__tur=tur, yuklama__holat="tayyor")
    if ruxsat is not None:
        qs = qs.filter(tp__tuman_id__in=ruxsat)
    if tuman_id:
        qs = qs.filter(tp__tuman_id=tuman_id)
    if brigada_id:
        qs = qs.filter(tp__brigada_id=brigada_id)
    rows = qs.values("yuklama__sana").annotate(**{"s_" + f: Sum(f) for f in SUM_FIELDS}).order_by("yuklama__sana")
    out = []
    for r in rows:
        d = hisobla({f: r["s_" + f] or 0 for f in SUM_FIELDS})
        d["sana"] = r["yuklama__sana"].strftime("%d.%m")
        d["sana_iso"] = r["yuklama__sana"].isoformat()
        out.append(d)
    return out[-limit:]


def oldingi_sana(tur, sana):
    s = [x for x in mavjud_sanalar(tur) if sana and x < sana]
    return s[-1] if s else None
