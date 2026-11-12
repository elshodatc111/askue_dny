"""CAS Excel fayllarini o'qish.

Muhim: ustun NOMLARIGA tayanilmaydi (CAS turli tilda yuklashi mumkin).
Fayl turi ustunlar soni va ustunlardagi qiymat ko'rinishiga (sana, IP, GPS, vaqt ...) qarab aniqlanadi,
ma'lumotlar esa ustun TARTIB RAQAMI bo'yicha o'qiladi.
"""
import datetime
import os
import re
import threading
import traceback
from collections import Counter, defaultdict

import openpyxl
from django.db import connection, transaction

from ..models import TP, Brigada, Hodim, Kuzatuv, TPSana, Tuman, Yuklama
from .names import (
    hodimlarni_ajrat, mas_kalit, pinflar, qisqa_nom, sozlash, tp_kalit, tuman_tartibi, norm,
)

BATCH = 2000
TARTIB = ["area", "dcu", "gprs", "nometer", "direct"]  # import tartibi: avval tuzilma

# ---- ustun joylashuvi (0 dan boshlab) ----
ONLINE_COLS = dict(esp=0, sub=1, feeder=2, tr=3, tur=4, raqam=5, holat=6, vaqt=7, operator=8, lat=9, lon=10, ip=11, mgr=15)
NOMETER_COLS = dict(esp=1, sub=2, feeder=3, tr=4, hisob=5, turi=6, abonent=7, raqam=8, aloqa=9, mgr=10, kun=12, gps=14, manzil=15)
DIRECT_COLS = dict(esp=1, sub=3, feeder=4, tr=5, raqam=6, hisob=7, turi=8, abonent=9, manzil=10, gps=12)
AREA_COLS = dict(esp=4, sub=6, feeder=8, tr=10, egasi=11, mgr=12, id=14, tel=15)

RE_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
RE_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
RE_GPS = re.compile(r"^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$")
RE_DT = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?")
RE_DT2 = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?")


class ImportXato(Exception):
    pass


# ------------------------------------------------------------------ o'qish
def _ochish(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    try:
        ws.reset_dimensions()  # ba'zi CAS fayllarida o'lcham noto'g'ri yoziladi
    except Exception:
        pass
    return wb, ws


def _bosh_qatorlar(path, n=16):
    wb, ws = _ochish(path)
    rows = []
    try:
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            rows.append(row)
            if i >= n:
                break
    finally:
        wb.close()
    return rows


def _toldirilgan(row):
    return [i for i, c in enumerate(row) if c not in (None, "") and str(c).strip() != ""]


def _ustun(row, i):
    return row[i] if i < len(row) else None


def parse_dt(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, datetime.date):
        return datetime.datetime(v.year, v.month, v.day)
    s = str(v)
    m = RE_DT.search(s)
    try:
        if m:
            d, mo, y, h, mi, se = m.groups()
            return datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(se or 0))
        m = RE_DT2.search(s)
        if m:
            y, mo, d, h, mi, se = m.groups()
            return datetime.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(se or 0))
    except ValueError:
        return None
    return None


def parse_gps(v):
    s = sozlash(v)
    if not s or not RE_GPS.match(s):
        return None, None
    a, b = [float(x) for x in s.split(",")]
    if 36 <= a <= 46 and 54 <= b <= 76:
        return a, b
    if 36 <= b <= 46 and 54 <= a <= 76:
        return b, a
    return None, None


def _son(v):
    try:
        return int(float(str(v).replace(" ", "").replace(",", ".")))
    except (ValueError, TypeError):
        return None


def sana_fayl_nomidan(nom):
    m = re.search(r"(\d{2})(\d{2})(20\d{2})_\d{6}", nom or "")
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})", nom or "")
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def aniqlash(path, fayl_nomi="", majburiy=None):
    """Fayl turini mazmundan aniqlaydi. {'tur', 'header', 'sana'} qaytaradi."""
    rows = _bosh_qatorlar(path)
    if not rows:
        raise ImportXato("Fayl bo'sh.")
    maxc = max(len(_toldirilgan(r)) for r in rows)
    header = None
    for i, r in enumerate(rows):
        t = _toldirilgan(r)
        farqli = len({sozlash(r[j]) for j in t})  # birlashtirilgan sarlavha qatori bir xil qiymat takrorlaydi
        if len(t) >= 8 and len(t) >= 0.6 * maxc and farqli >= 0.8 * len(t):
            header = i
            break
    if header is None:
        raise ImportXato("Jadval sarlavhasi topilmadi.")
    ncols = _toldirilgan(rows[header])[-1] + 1
    data = [r for r in rows[header + 1 :] if _toldirilgan(r)]
    if not data:
        raise ImportXato("Faylda ma'lumot qatorlari yo'q.")

    def sampl(i):
        return [sozlash(_ustun(r, i)) for r in data]

    sana = None
    for r in rows[:header]:
        for c in r:
            if isinstance(c, datetime.datetime):
                sana = c.date()
    tur = None
    if majburiy:
        tur = "online" if majburiy in ("dcu", "gprs") else majburiy
    elif ncols >= 18 and any(RE_IP.match(x) for x in sampl(11)) and any(parse_dt(_ustun(r, 7)) for r in data):
        tur = "online"
    elif 15 <= ncols <= 17:
        if any(RE_TIME.match(x) or isinstance(_ustun(r, 13), datetime.time) for r, x in zip(data, sampl(13))) and any(_son(x) is not None for x in sampl(12)):
            tur = "nometer"
        elif any(re.fullmatch(r"\d{3,6}", x) for x in sampl(1)) and any(re.fullmatch(r"\d{3,6}", x) for x in sampl(3)):
            tur = "area"
    elif 12 <= ncols <= 14:
        if any(RE_GPS.match(x) or x.strip() == "," for x in sampl(12)):
            tur = "direct"
    if not tur:
        raise ImportXato("Fayl turi aniqlanmadi (CAS hisobotlaridan biri emas).")
    if tur == "online":
        tur = _dcu_yoki_gprs(rows[header + 1 :])
    if majburiy in ("dcu", "gprs"):
        tur = majburiy
    if tur in ("dcu", "gprs"):
        if not sana:
            sana = sana_fayl_nomidan(fayl_nomi)
    return {"tur": tur, "header": header, "sana": sana, "ncols": ncols}


def _dcu_yoki_gprs(data):
    dcu = gprs = 0
    for r in data[:300]:
        t = sozlash(_ustun(r, 4)).lower()
        if re.search(r"dcu|концентр|konsentr|concentr", t):
            dcu += 1
        elif t:
            gprs += 1
    if dcu or gprs:
        return "dcu" if dcu >= gprs else "gprs"
    n = sozlash(_ustun(data[0], 5)) if data else ""
    return "dcu" if n.startswith("1292") else "gprs"


def qatorlar(path, header):
    wb, ws = _ochish(path)
    try:
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i <= header:
                continue
            if any(c not in (None, "") for c in row):
                yield row
    finally:
        wb.close()


# ------------------------------------------------------------------ tasniflash
def holat_tasnif(v):
    s = sozlash(v).lower()
    if not s:
        return "noma'lum"
    if any(k in s for k in ("offline", "off-line", "офлайн", "оффлайн", "uzil", "узил", "o'chiq", "ochiq")):
        return "offline"
    if s.startswith("on") or "онлайн" in s or "ulangan" in s or "уланган" in s:
        return "online"
    return "noma'lum"


def turi_tasnif(v):
    s = sozlash(v).lower()
    if any(k in s for k in ("resid", "аҳол", "ахол", "насел", "aholi", "быт", "maishiy")):
        return "aholi"
    if any(k in s for k in ("balan", "баланс")):
        return "balans"
    if any(k in s for k in ("indust", "ulgurj", "улгурж", "оптов", "пром", "sanoat", "whole", "юр", "yurid")):
        return "ulgurji"
    return "boshqa"


def bucket(kun):
    if kun is None or kun <= 1:
        return "b0"
    if kun <= 7:
        return "b1"
    if kun <= 30:
        return "b2"
    if kun <= 90:
        return "b3"
    return "b4"


# ------------------------------------------------------------------ TP / tuman aniqlash
def _tel(s):
    p = [x.strip() for x in re.split(r"[,;]", s or "") if x.strip() and x.strip().lower() not in ("null", "none", "nan")]
    return ", ".join(p)


def _kes(s, n):
    return (s or "")[:n]


class Resolver:
    def __init__(self):
        self.tumanlar = {norm(t.nom): t for t in Tuman.objects.all()}
        self.tplar = {tp.kalit: tp for tp in TP.objects.only("id", "kalit", "brigada_id", "tuman_id")}
        self.brig = {(b.tuman_id, b.manba_kalit): b.id for b in Brigada.objects.exclude(manba_kalit="")}

    def tuman(self, nom):
        nom = sozlash(nom) or "Noma'lum"
        t = self.tumanlar.get(norm(nom))
        if t is None:
            t = Tuman.objects.create(nom=_kes(nom, 120), qisqa=_kes(qisqa_nom(nom), 60), tartib=tuman_tartibi(nom))
            self.tumanlar[norm(nom)] = t
        return t

    def tayyorla(self, yozuvlar):
        """Yozuvlardagi barcha TP larni (yo'q bo'lsa) ommaviy yaratadi."""
        yangi = {}
        for r in yozuvlar:
            t = self.tuman(r["esp"])
            k = tp_kalit(t.nom, r["sub"], r["feeder"], r["tr"])
            r["_k"] = k
            r["_t"] = t.id
            if k not in self.tplar and k not in yangi:
                bid = self.brig.get((t.id, mas_kalit(r.get("mgr", "")))) if r.get("mgr") else None
                yangi[k] = TP(
                    tuman=t, kalit=k, podstansiya=_kes(r["sub"], 150), feeder=_kes(r["feeder"], 150),
                    raqam=_kes(r["tr"], 60), egasi=_kes(r.get("egasi", ""), 40), brigada_id=bid,
                )
        if yangi:
            items = list(yangi.values())
            for i in range(0, len(items), BATCH):
                TP.objects.bulk_create(items[i : i + BATCH], ignore_conflicts=True)
            kalitlar = list(yangi.keys())
            for i in range(0, len(kalitlar), 900):
                for tp in TP.objects.filter(kalit__in=kalitlar[i : i + 900]).only("id", "kalit", "brigada_id", "tuman_id"):
                    self.tplar[tp.kalit] = tp
        return len(yangi)

    def tp(self, r):
        return self.tplar[r["_k"]]


def _tp_maydonlar(row, c):
    return dict(
        esp=sozlash(_ustun(row, c["esp"])), sub=sozlash(_ustun(row, c["sub"])),
        feeder=sozlash(_ustun(row, c["feeder"])), tr=sozlash(_ustun(row, c["tr"])),
        mgr=sozlash(_ustun(row, c["mgr"])) if "mgr" in c else "",
    )


def _bos():
    return dict(jami=0, online=0, b0=0, b1=0, b2=0, b3=0, b4=0, aholi=0, ulgurji=0, balans=0)


def _tpsana_yoz(yuklama, agg):
    items = [TPSana(yuklama=yuklama, tp_id=tp_id, **a) for tp_id, a in agg.items()]
    for i in range(0, len(items), BATCH):
        TPSana.objects.bulk_create(items[i : i + BATCH])


def _kuz_yoz(items):
    for i in range(0, len(items), BATCH):
        Kuzatuv.objects.bulk_create(items[i : i + BATCH])


# ------------------------------------------------------------------ turlar bo'yicha import
def import_area(path, header, yuklama, res):
    recs = []
    for row in qatorlar(path, header):
        r = _tp_maydonlar(row, AREA_COLS)
        if not r["tr"] and not r["sub"]:
            continue
        r["egasi"] = sozlash(_ustun(row, AREA_COLS["egasi"]))
        r["id"] = sozlash(_ustun(row, AREA_COLS["id"]))
        r["tel"] = sozlash(_ustun(row, AREA_COLS["tel"]))
        recs.append(r)
    # takror TP larni olib tashlash
    for r in recs:
        res.tuman(r["esp"])
    # 1) yangi brigadalar
    mas = defaultdict(Counter)  # tuman_id -> {mgr: tp soni}
    info = {}
    for r in recs:
        if not r["mgr"]:
            continue
        t = res.tuman(r["esp"])
        mas[t.id][r["mgr"]] += 1
        info.setdefault((t.id, r["mgr"]), (r["id"], r["tel"]))
    yangi_br = 0
    for tid, cnt in mas.items():
        mavjud = list(Brigada.objects.filter(tuman_id=tid))
        raqam = max([b.raqam for b in mavjud], default=0)
        for mgr, _soni in cnt.most_common():
            k = mas_kalit(mgr)
            if (tid, k) in res.brig:
                continue
            raqam += 1
            idr, tel = info[(tid, mgr)]
            b = Brigada.objects.create(tuman_id=tid, raqam=raqam, nom=f"Brigada {raqam}", manba=_kes(mgr, 500), manba_kalit=k, telefon=_kes(_tel(tel), 200))
            ismlar = hodimlarni_ajrat(mgr)
            ids = pinflar(idr)
            for j, ism in enumerate(ismlar):
                Hodim.objects.create(brigada=b, ism=_kes(ism, 200), pinfl=ids[j] if len(ids) == len(ismlar) else "")
            res.brig[(tid, k)] = b.id
            yangi_br += 1
    # 2) TP lar
    yangi_tp = res.tayyorla(recs)
    # 3) brigadasi yo'q TP larga brigada biriktirish
    upd = []
    korilgan = set()
    for r in recs:
        tp = res.tp(r)
        if tp.id in korilgan:
            continue
        korilgan.add(tp.id)
        if tp.brigada_id is None and r["mgr"]:
            bid = res.brig.get((tp.tuman_id, mas_kalit(r["mgr"])))
            if bid:
                tp.brigada_id = bid
                upd.append(tp)
    for i in range(0, len(upd), BATCH):
        TP.objects.bulk_update(upd[i : i + BATCH], ["brigada"])
    yuklama.qatorlar = len(korilgan)
    return f"{len(korilgan)} ta TP o'qildi, {yangi_tp} ta yangi TP, {yangi_br} ta yangi brigada."


def import_online(path, header, yuklama, res):
    c = ONLINE_COLS
    sana = yuklama.sana
    recs = []
    for row in qatorlar(path, header):
        r = _tp_maydonlar(row, c)
        r["raqam"] = sozlash(_ustun(row, c["raqam"]))
        if not r["raqam"]:
            continue
        r["holat"] = holat_tasnif(_ustun(row, c["holat"]))
        r["vaqt"] = parse_dt(_ustun(row, c["vaqt"]))
        r["operator"] = sozlash(_ustun(row, c["operator"]))
        r["ip"] = sozlash(_ustun(row, c["ip"]))
        la, lo = _ustun(row, c["lat"]), _ustun(row, c["lon"])
        try:
            la, lo = float(la), float(lo)
            r["lat"], r["lon"] = (la, lo) if (36 <= la <= 46 and 54 <= lo <= 76) else (None, None)
        except (TypeError, ValueError):
            r["lat"] = r["lon"] = None
        recs.append(r)
    res.tayyorla(recs)
    agg = defaultdict(_bos)
    kuz = []
    for r in recs:
        tp = res.tp(r)
        a = agg[tp.id]
        a["jami"] += 1
        if r["holat"] == "online":
            a["online"] += 1
        elif r["holat"] == "offline":
            kun = max((sana - r["vaqt"].date()).days, 0) if r["vaqt"] else None
            a[bucket(kun)] += 1
            kuz.append(Kuzatuv(
                yuklama=yuklama, tp_id=tp.id, raqam=_kes(r["raqam"], 40), kun=kun, vaqt=r["vaqt"],
                operator=_kes(r["operator"], 30), ip=_kes(r["ip"], 45), lat=r["lat"], lon=r["lon"],
            ))
    _tpsana_yoz(yuklama, agg)
    _kuz_yoz(kuz)
    yuklama.qatorlar = len(recs)
    onl = sum(1 for r in recs if r["holat"] == "online")
    return f"{len(recs)} ta qurilma: {onl} online, {len(kuz)} offline."


def import_nometer(path, header, yuklama, res):
    c = NOMETER_COLS
    recs = []
    for row in qatorlar(path, header):
        r = _tp_maydonlar(row, c)
        r["raqam"] = sozlash(_ustun(row, c["raqam"]))
        if not r["raqam"]:
            continue
        r["kun"] = _son(_ustun(row, c["kun"]))
        r["turi"] = turi_tasnif(_ustun(row, c["turi"]))
        r["hisob"] = sozlash(_ustun(row, c["hisob"]))
        r["abonent"] = sozlash(_ustun(row, c["abonent"]))
        r["aloqa"] = sozlash(_ustun(row, c["aloqa"]))
        r["manzil"] = sozlash(_ustun(row, c["manzil"]))
        r["lat"], r["lon"] = parse_gps(_ustun(row, c["gps"]))
        recs.append(r)
    res.tayyorla(recs)
    agg = defaultdict(_bos)
    kuz = []
    for r in recs:
        tp = res.tp(r)
        a = agg[tp.id]
        a["jami"] += 1
        a[bucket(r["kun"])] += 1
        if r["turi"] in ("aholi", "ulgurji", "balans"):
            a[r["turi"]] += 1
        kuz.append(Kuzatuv(
            yuklama=yuklama, tp_id=tp.id, raqam=_kes(r["raqam"], 40), kun=r["kun"], abonent=_kes(r["abonent"], 200),
            hisob=_kes(r["hisob"], 40), abonent_turi=r["turi"], aloqa_turi=_kes(r["aloqa"], 10),
            manzil=_kes(r["manzil"], 300), lat=r["lat"], lon=r["lon"],
        ))
    _tpsana_yoz(yuklama, agg)
    _kuz_yoz(kuz)
    yuklama.qatorlar = len(recs)
    return f"{len(recs)} ta aloqadan chiqib ketgan hisoblagich."


def import_direct(path, header, yuklama, res):
    c = DIRECT_COLS
    recs = []
    for row in qatorlar(path, header):
        r = _tp_maydonlar(row, c)
        r["raqam"] = sozlash(_ustun(row, c["raqam"]))
        if not r["raqam"]:
            continue
        r["turi"] = turi_tasnif(_ustun(row, c["turi"]))
        r["hisob"] = sozlash(_ustun(row, c["hisob"]))
        r["abonent"] = sozlash(_ustun(row, c["abonent"]))
        r["manzil"] = sozlash(_ustun(row, c["manzil"]))
        r["lat"], r["lon"] = parse_gps(_ustun(row, c["gps"]))
        recs.append(r)
    res.tayyorla(recs)
    agg = defaultdict(_bos)
    kuz = []
    for r in recs:
        tp = res.tp(r)
        a = agg[tp.id]
        a["jami"] += 1
        if r["turi"] in ("aholi", "ulgurji", "balans"):
            a[r["turi"]] += 1
        kuz.append(Kuzatuv(
            yuklama=yuklama, tp_id=tp.id, raqam=_kes(r["raqam"], 40), abonent=_kes(r["abonent"], 200),
            hisob=_kes(r["hisob"], 40), abonent_turi=r["turi"], manzil=_kes(r["manzil"], 300), lat=r["lat"], lon=r["lon"],
        ))
    _tpsana_yoz(yuklama, agg)
    _kuz_yoz(kuz)
    yuklama.qatorlar = len(recs)
    return f"{len(recs)} ta to'g'ridan-to'g'ri ulanish."


IMPORTLAR = {"area": import_area, "dcu": import_online, "gprs": import_online, "nometer": import_nometer, "direct": import_direct}


def bajar(yuklama_id, path, header):
    """Bitta yuklamani to'liq bajaradi (tranzaksiyada)."""
    y = Yuklama.objects.get(pk=yuklama_id)
    try:
        res = Resolver()
        with transaction.atomic():
            xabar = IMPORTLAR[y.tur](path, header, y, res)
            y.holat = "tayyor"
            y.xabar = xabar
            y.save()
            # shu tur va sana uchun eski yuklamalarni almashtirish
            Yuklama.objects.filter(tur=y.tur, sana=y.sana).exclude(pk=y.pk).delete()
    except Exception as e:  # noqa
        y = Yuklama.objects.get(pk=yuklama_id)
        y.holat = "xato"
        y.xabar = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        y.save()


def _ishchi(ishlar):
    try:
        for ish in sorted(ishlar, key=lambda j: TARTIB.index(j["tur"])):
            try:
                bajar(ish["yuklama_id"], ish["path"], ish["header"])
            finally:
                try:
                    os.remove(ish["path"])
                except OSError:
                    pass
    finally:
        connection.close()


def fonda_boshlash(ishlar):
    t = threading.Thread(target=_ishchi, args=(ishlar,), daemon=True)
    t.start()
    return t


def sinxron(ishlar):
    for ish in sorted(ishlar, key=lambda j: TARTIB.index(j["tur"])):
        bajar(ish["yuklama_id"], ish["path"], ish["header"])
