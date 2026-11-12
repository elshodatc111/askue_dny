"""Respublika dinamikasi: tayyor PDF hisobotni o'qish, sanalar bo'yicha solishtirish, jadval tuzish.

Respublikadan har ish kuni 9 betli PDF keladi. Dasturga kerakli betlar: 1, 2, 3, 4, 6, 7, 8 (jadvallar).
5-bet (diagrammalar) va 9-bet (SmartApp) o'qilmaydi.

PDF dagi strelkalar (↑↓) oy boshiga nisbatan hisoblangan; ularni saqlamaymiz - faqat sof sonlar saqlanadi va
farq tanlangan solishtirish sanasiga nisbatan qayta hisoblanadi.

Ustunlar PDF dagi son o'ng chekkasining (x1) joyiga qarab aniqlanadi: har bir jadval har kuni bir xil shablondan
chiqadi, shuning uchun ustunlarning joyi o'zgarmaydi.
"""
import datetime
import json
import re

try:  # PDF o'qish uchun (pip install pdfplumber)
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

ARROW = "↑↓"
YANGI_BETLAR = 8  # kamida shuncha bet bo'lishi kerak (8-betgacha jadvallar)
TOLERANS = 22.0  # son va ustun markazi orasidagi eng katta masofa (pt)

# ------------------------------------------------------------------ shablonlar


def _u(key, anchor, *yol, d=False, p=False, dbase=None):
    """Ustun tavsifi. d=True: yonida strelkali o'zgarish ustuni ham bor (shu ustun bo'yicha yoki dbase bo'yicha)."""
    return {"key": key, "anchor": anchor, "yol": yol, "d": d, "p": p, "dbase": dbase or key}


def _dl(key, base, *yol):
    """Alohida (qiymatdan keyin turuvchi) o'zgarish ustuni: base ustun bo'yicha farq."""
    return {"key": key, "anchor": None, "yol": yol, "d": False, "p": False, "dbase": base}


# har bir bet: (kod, PDF dagi bet indeksi (0 dan), qisqa nom, sarlavha, "DINAMIKA"/"MA'LUMOT", ustunlar)
_R1 = [
    _u("tr", 161, "Dasturda mavjud transformatorlar soni"),
    _u("all", 202, "Konsentratorlar", "CAS ga yuklangan"),
    _u("on", 244, "Konsentratorlar", "Online"),
    _u("off", 275, "Konsentratorlar", "Offline (jami)"),
    _u("off3", 307, "Konsentratorlar", "shundan 3 kundan ortiq", "soni", d=True),
    _u("c0", 380, "Konsentratorlarning obxod olish darajasi bo'yicha soni", "0%", "soni", d=True),
    _u("c1", 454, "Konsentratorlarning obxod olish darajasi bo'yicha soni", "1-30%", "soni", d=True),
    _u("c30", 528, "Konsentratorlarning obxod olish darajasi bo'yicha soni", "30-50%", "soni", d=True),
    _u("c50", 602, "Konsentratorlarning obxod olish darajasi bo'yicha soni", "50-80%", "soni", d=True),
    _u("c80", 676, "Konsentratorlarning obxod olish darajasi bo'yicha soni", "80-100%", "soni", d=True),
    _u("nomet", 749, "Iste'molchi biriktirilmagan konsentratorlar soni"),
]
_G2 = "Aloqadan chiqib ketgan hisoblagichlar soni"
_R2 = [
    _u("aloqa", 184, "Aloqaga chiqqan hisoblagichlar soni"),
    _u("jami", 225, _G2, "Jami", "", "soni"),
    _u("foiz", 246, _G2, "Jami", "", "%", p=True),
    _dl("jami_d", "jami", _G2, "Jami", "", "↑↓"),
    _u("ahol", 328, _G2, "Iste'molchi turi kesimida", "Aholi", "soni", d=True),
    _u("ulg", 400, _G2, "Iste'molchi turi kesimida", "Ulgurji", "soni", d=True),
    _u("bal", 473, _G2, "Iste'molchi turi kesimida", "Balans", "soni", d=True),
    _u("k7", 539, _G2, "Vaqtlar kesimida", "7-30 kun", "soni", d=True),
    _u("k30", 612, _G2, "Vaqtlar kesimida", "1-3 oy", "soni", d=True),
    _u("k90", 687, _G2, "Vaqtlar kesimida", "3 oydan ortiq", "soni", d=True),
]
_G3 = "Tarmoqdan uzilgan hisoblagichlar"
_R3 = [
    _u("aloqa", 209, "Aloqaga chiqqan hisoblagichlar soni"),
    _u("jami", 256, _G3, "Jami", "", "soni"),
    _u("foiz", 288, _G3, "Jami", "", "%", p=True),
    _dl("jami_d", "jami", _G3, "Jami", "", "↑↓"),
    _u("k4", 396, _G3, "shundan", "4-7 kun", "soni", d=True),
    _u("k7", 485, _G3, "shundan", "7-30 kun", "soni", d=True),
    _u("k30", 574, _G3, "shundan", "30 kundan ortiq", "soni", d=True),
    _u("direct", 663, "To'g'ridan-to'g'ri ulanishlar soni (primichka)", "", "", "soni", d=True),
]
_B4 = "Balans hisoblagichlar"
_R4 = [
    _u("loyiha", 165, _B4, "Loyiha doirasida"),
    _u("cas", 212, _B4, "CAS ga yuklangan"),
    _u("bir", 259, _B4, "Obxod olish ko'rsatkichi", "Bir marta obxod olgan"),
    _u("umuman", 304, _B4, "Obxod olish ko'rsatkichi", "Umuman obxod olmagan"),
    _u("uch", 352, _B4, "Obxod olish ko'rsatkichi", "shundan 3 kundan ortiq obxod olmagan", "soni", d=True),
    _u("muam", 435, "MUAMMOLI TRANSFORMATORLAR", "", "", "soni", d=True),
    _u("quvvat", 518, "shundan", "Quvvati yuklanmagan"),
    _u("tt", 564, "shundan", "TT noto'g'ri ulangan yoki nominali xato"),
    _u("sxema", 607, "shundan", "Sxemasi xato yoki cos=0"),
    _u("balaloqa", 655, "shundan", "Balans hisoblagich aloqaga chiqmagan"),
    _u("tp0", 704, "shundan", "TP nagruzkasi 0%"),
    _u("tp150", 748, "shundan", "TP nagruzkasi 150%"),
]
_G6 = "shundan"
_R6 = [
    _u("j_ab", 157, "Jami hisoblagichlar", "Jami soni"),
    _u("j_ob", 204, "Jami hisoblagichlar", "shundan obxod olgan"),
    _u("j_p", 237, "Jami hisoblagichlar", "%", p=True),
    _dl("j_d", "j_ob", "Jami hisoblagichlar", "↑↓"),
    _u("a_ab", 327, _G6, "Aholi iste'molchilari", "Jami soni"),
    _u("a_ob", 375, _G6, "Aholi iste'molchilari", "shundan obxod olgan"),
    _u("a_p", 407, _G6, "Aholi iste'molchilari", "%", p=True),
    _dl("a_d", "a_ob", _G6, "Aholi iste'molchilari", "↑↓"),
    _u("u_ab", 498, _G6, "Ulgurji iste'molchilar", "Jami soni"),
    _u("u_ob", 545, _G6, "Ulgurji iste'molchilar", "shundan obxod olgan"),
    _u("u_p", 578, _G6, "Ulgurji iste'molchilar", "%", p=True),
    _dl("u_d", "u_ob", _G6, "Ulgurji iste'molchilar", "↑↓"),
    _u("b_ab", 659, _G6, "Balans hisoblagichlar", "Jami soni"),
    _u("b_ob", 689, _G6, "Balans hisoblagichlar", "shundan obxod olgan"),
    _u("b_p", 722, _G6, "Balans hisoblagichlar", "%", p=True),
    _dl("b_d", "b_ob", _G6, "Balans hisoblagichlar", "↑↓"),
]
_G7 = "shundan: balans va iste'molchilar hisoblagichlari o'rtasidagi tafovut"
_R7 = [
    _u("tr", 163, "CAS dasturidagi transformatorlar", "Jami soni"),
    _u("rezerv", 215, "CAS dasturidagi transformatorlar", "shundan rezervda (2x seksiyali)"),
    _u("balans", 267, "Balans hisoblagich o'rnatilgan TP lar soni"),
    _u("manfiy", 313, _G7, "Manfiy", "soni", d=True),
    _u("f0", 394, _G7, "0%", "soni", d=True),
    _u("f10", 475, _G7, "1-10%", "soni", d=True),
    _u("f20", 555, _G7, "10-20%", "soni", d=True),
    _u("f50", 636, _G7, "20-50%", "soni", d=True),
    _u("f100", 717, _G7, "50-100%", "soni", d=True),
]
_BG = "«Billing» dasturida mavjud"
_CG = "CAS dasturida mavjud, Billing dasturiga kiritilmagan hisoblagichlar"
_R8 = [
    _u("bill", 162, "Billing dasturi bilan ma'lumot almashmaetgan hisoblagichlar", "soni", d=True),
    _u("hisob", 226, "shundan", "Iste'molchi hisob raqami mos emas", "soni", d=True),
    _u("tur", 288, "shundan", "Iste'molchi turi mos emas", "soni", d=True),
    _u("casyoq", 359, "shundan", "CAS dasturida mavjud bo'lmagan hisoblagichlar", "soni", d=True),
    _u("askue", 429, _BG, "ASKUE ga mos bo'lmagan hisoblagichlar", "soni", d=True),
    _u("ahol", 499, _BG, "shundan", "Aholi"),
    _u("ulg", 540, _BG, "shundan", "Ulgurji"),
    _u("dubl", 578, _BG, "Dublikat hisoblagichlar", "soni", d=True),
    _u("casbor", 643, _CG, "Hisoblagichlar jami soni", "soni", d=True),
    _u("o3", 712, _CG, "shundan obxod olgan", "3 kun ichida"),
    _u("o30", 752, _CG, "shundan obxod olgan", "30 kun ichida"),
]

SAHIFALAR = {
    "r1": {"bet": 0, "nom": "Konsentratorlar", "tur": "DINAMIKA", "ustunlar": _R1,
           "sarlavha": "Qashqadaryo HETK hududida CAS dasturida mavjud konsentratorlar holati bo'yicha"},
    "r2": {"bet": 1, "nom": "Aloqadan chiqib ketganlar", "tur": "DINAMIKA", "ustunlar": _R2,
           "sarlavha": "Qashqadaryo HETK da CAS dasturida aloqaga chiqmagan hisoblagichlar bo'yicha"},
    "r3": {"bet": 2, "nom": "Tarmoqdan uzilganlar", "tur": "DINAMIKA", "ustunlar": _R3,
           "sarlavha": "Qashqadaryo HETK da CAS dasturida tarmoqdan uzilgan hisoblagichlar bo'yicha"},
    "r4": {"bet": 3, "nom": "Balans va TP yuklamasi", "tur": "DINAMIKA", "ustunlar": _R4,
           "sarlavha": "Qashqadaryo HETK hududida CAS dasturidagi balans hisoblagichlar va transformatorlar yuklamasi bo'yicha"},
    "r6": {"bet": 5, "nom": "48 soatda obxod", "tur": "MA'LUMOT", "ustunlar": _R6,
           "sarlavha": "Qashqadaryo HETK hududida 48 soat ichida obxod bergan hisoblagichlar bo'yicha"},
    "r7": {"bet": 6, "nom": "Balans tafovuti", "tur": "DINAMIKA", "ustunlar": _R7,
           "sarlavha": "Qashqadaryo HETK hududida balans va iste'molchilar hisoblagichlari o'rtasidagi tafovutlar bo'yicha"},
    "r8": {"bet": 7, "nom": "Billing va CAS", "tur": "MA'LUMOT", "ustunlar": _R8,
           "sarlavha": "Billing va CAS dasturlarida tafovutga ega hisoblagichlar bo'yicha"},
}
SAHIFA_TARTIB = list(SAHIFALAR)


# ustun matni rangi (asl hisobotdagidek): g - yashil, r - qizil, b - ko'k, o - to'q sariq
RANG = {
    ("r1", "off"): "r", ("r1", "off3"): "r",
    ("r2", "aloqa"): "g", ("r2", "jami"): "r", ("r2", "foiz"): "r", ("r2", "bal"): "o",
    ("r3", "aloqa"): "g", ("r3", "jami"): "r", ("r3", "foiz"): "r", ("r3", "direct"): "r",
    ("r4", "bir"): "g", ("r4", "umuman"): "r", ("r4", "uch"): "r", ("r4", "muam"): "b", ("r4", "tp0"): "o", ("r4", "tp150"): "b",
    ("r6", "j_ob"): "g", ("r6", "a_ob"): "g", ("r6", "u_ob"): "g", ("r6", "b_ob"): "g",
    ("r7", "balans"): "g", ("r7", "manfiy"): "r", ("r7", "f0"): "r", ("r7", "f10"): "g", ("r7", "f20"): "b", ("r7", "f50"): "o", ("r7", "f100"): "r",
    ("r8", "bill"): "r", ("r8", "dubl"): "o", ("r8", "casbor"): "g", ("r8", "o3"): "b", ("r8", "o30"): "b",
}


def _ustunlar_royxati(kod):
    """Ko'rsatiladigan barcha ustunlar (qiymat + o'zgarish) tartibda: [{key, kind, yol, base, p}]."""
    res = []
    for u in SAHIFALAR[kod]["ustunlar"]:
        if u["anchor"] is None:  # tayyor delta ustuni (6-bet)
            res.append({"key": u["key"], "kind": "d", "yol": u["yol"], "base": u["dbase"], "p": False})
            continue
        res.append({"key": u["key"], "kind": "p" if u["p"] else "n", "yol": u["yol"], "base": None, "p": u["p"],
                    "rang": RANG.get((kod, u["key"]), "")})
        if u["d"]:
            res.append({"key": u["key"] + "_d", "kind": "d", "yol": u["yol"][:-1] + ("↑↓",), "base": u["dbase"], "p": False})
    return res


# ------------------------------------------------------------------ PDF o'qish
_SANA_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def _son(s):
    s = s.replace("−", "-")
    pct = s.endswith("%")
    t = s.rstrip("%").replace(",", ".").replace(" ", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if (pct or "." in t) else int(v)


def _qatorlar(pg):
    ws = [w for w in pg.extract_words(x_tolerance=1.5, y_tolerance=2) if "[" not in w["text"] and "]" not in w["text"]]
    ws.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in ws:
        for L in lines:
            if abs(L[0] - w["top"]) <= 2.5:
                L[1].append(w)
                break
        else:
            lines.append([w["top"], [w]])
    out = []
    for top, L in sorted(lines):
        L.sort(key=lambda w: w["x0"])
        out.append((top, L))
    return out


def _elementlar(L):
    """Qator tokenlari -> (yorliq, [(x1, qiymat)]). Strelkali o'zgarishlar tashlab yuboriladi."""
    toks = [(w["text"], w["x0"], w["x1"]) for w in L]
    label = []
    i = 0
    while i < len(toks) and _son(toks[i][0]) is None and toks[i][0] not in ARROW and toks[i][0] != "-":
        label.append(toks[i][0])
        i += 1
    items = []
    while i < len(toks):
        t, x0, x1 = toks[i]
        if t in ARROW:
            i += 1
            px = x1
            while i < len(toks) and toks[i][1] - px <= 3.2 and _son(toks[i][0]) is not None:
                px = toks[i][2]
                i += 1
            continue
        if t == "-" or _son(t) is None:
            i += 1
            continue
        s = t
        px = x1
        i += 1
        while i < len(toks) and toks[i][1] - px <= 3.2 and re.fullmatch(r"\d+", toks[i][0]) and re.fullmatch(r"-?\d+", s):
            s += toks[i][0]
            px = toks[i][2]
            i += 1
        items.append((px, _son(s)))
    return " ".join(label), items


def _norm(nom):
    return re.sub(r"\s+", " ", nom.replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("`", "'")).strip().lower()


def _jami_mi(nom):
    return _norm(nom) in ("жами", "jami")


def _bet_oqi(pg, kod):
    """Bitta betdan jadval qatorlarini o'qiydi: [{nom, jami, v:{key: son}}], ogohlantirishlar."""
    spec = SAHIFALAR[kod]["ustunlar"]
    ank = [(u["anchor"], u["key"]) for u in spec if u["anchor"] is not None]
    pfoiz = {u["key"] for u in spec if u["p"]}
    qat = _qatorlar(pg)
    jt = None
    for top, L in qat:
        if top < 225:
            continue
        lab, items = _elementlar(L)
        if _jami_mi(lab) and items:
            jt = top
            break
    if jt is None:
        return None, ["Jadval topilmadi (\"Jami\" qatori yo'q)."]
    rows, ogoh = [], []
    oxirgi = jt
    for top, L in qat:
        if top < jt - 1:
            continue
        if top - oxirgi > 40:
            break
        if L[0]["x0"] > 125:
            continue
        lab, items = _elementlar(L)
        if not lab or _son(lab.split()[0]) is not None:
            continue
        oxirgi = top
        v = {}
        for x, val in items:
            k, d = min(((kk, abs(x - a)) for a, kk in ank), key=lambda t: t[1])
            if d > TOLERANS:
                ogoh.append(f"{lab}: tushunarsiz katak (x={x:.0f}).")
                continue
            if k in v:
                ogoh.append(f"{lab}: ikki marta qiymat ({k}).")
                continue
            if k in pfoiz and val is not None:
                val = round(float(val), 2)
            v[k] = val
        rows.append({"nom": "Jami" if _jami_mi(lab) else lab, "jami": _jami_mi(lab), "v": v})
    return rows, ogoh


def _tekshir(kod, rows):
    """Tuman qatorlari yig'indisi 'Jami' qatoriga mos kelishini tekshiradi (foizlardan tashqari)."""
    ogoh = []
    jami = next((r for r in rows if r["jami"]), None)
    tum = [r for r in rows if not r["jami"]]
    if not jami or not tum:
        return ["Jadvalda tuman qatorlari yoki \"Jami\" qatori topilmadi."]
    for u in SAHIFALAR[kod]["ustunlar"]:
        if u["anchor"] is None or u["p"]:
            continue
        k = u["key"]
        yig = sum((r["v"].get(k) or 0) for r in tum)
        j = jami["v"].get(k) or 0
        if yig != j:
            ogoh.append(f"{SAHIFALAR[kod]['nom']}: \"{k}\" ustuni yig'indisi ({yig}) \"Jami\" ({j}) ga teng emas.")
    return ogoh


def hisobot_sanasi(pdf):
    """Birinchi betdagi 'Динамика: 01.11.2026 - 12.11.2026' dan oxirgi sanani oladi."""
    pg = pdf.pages[0]
    matn = pg.extract_text() or ""
    for ln in matn.splitlines():
        if "Динамика" in ln or "Dinamika" in ln:
            d = _SANA_RE.findall(ln)
            if d:
                dd, mm, yy = d[-1]
                try:
                    return datetime.date(int(yy), int(mm), int(dd))
                except ValueError:
                    pass
    for top, L in _qatorlar(pg):
        if top < 175:
            for w in L:
                m = _SANA_RE.fullmatch(w["text"])
                if m:
                    try:
                        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    except ValueError:
                        pass
    return None


def oqi(manba, fayl_nomi="", jarayon=None):
    """PDF ni o'qiydi (jarayon(i, n) - har bir jadval o'qilgach chaqiriladi). Qaytaradi: {"sana": date|None, "malumot": {kod: [qatorlar]}, "ogohlantirish": [...], "xato": str|None}"""
    res = {"sana": None, "malumot": {}, "ogohlantirish": [], "xato": None}
    if pdfplumber is None:
        res["xato"] = "PDF o'qish kutubxonasi (pdfplumber) o'rnatilmagan. setup.bat ni qayta ishga tushiring."
        return res
    try:
        pdf = pdfplumber.open(manba)
    except Exception as e:  # noqa: BLE001
        res["xato"] = f"PDF ochilmadi: {e}"
        return res
    try:
        if len(pdf.pages) < YANGI_BETLAR:
            res["xato"] = f"PDF da kamida {YANGI_BETLAR} bet bo'lishi kerak (hozir {len(pdf.pages)} ta). Bu respublika dinamikasi fayli emas."
            return res
        res["sana"] = hisobot_sanasi(pdf)
        if not res["sana"]:
            m = _SANA_RE.search(fayl_nomi or "")
            if m:
                try:
                    res["sana"] = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    res["ogohlantirish"].append("Sana PDF ichidan topilmadi, fayl nomidan olindi.")
                except ValueError:
                    pass
        elif fayl_nomi:
            m = _SANA_RE.search(fayl_nomi)
            if m:
                try:
                    fs = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    if fs != res["sana"]:
                        res["ogohlantirish"].append(
                            f"Fayl nomidagi sana ({fs:%d.%m.%Y}) PDF ichidagi sana ({res['sana']:%d.%m.%Y}) bilan mos emas; PDF dagi sana olindi.")
                except ValueError:
                    pass
        for n_, (kod, spec) in enumerate(SAHIFALAR.items(), 1):
            rows, og = _bet_oqi(pdf.pages[spec["bet"]], kod)
            if rows is None:
                res["xato"] = f"{spec['bet'] + 1}-betdan ({spec['nom']}) jadval o'qilmadi."
                return res
            res["malumot"][kod] = rows
            res["ogohlantirish"] += [f"{spec['bet'] + 1}-bet: {x}" for x in og]
            res["ogohlantirish"] += _tekshir(kod, rows)
            if jarayon:
                jarayon(n_, len(SAHIFALAR))
    finally:
        pdf.close()
    return res


def malumot_json(m):
    return json.dumps(m, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ jadval tuzish
def _fmt(v, p=False):
    if v is None:
        return ""
    if p:
        if float(v).is_integer():
            return f"{int(v)}%"
        return f"{v:.1f}".replace(".", ",") + "%"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}".replace(".", ",")
    return f"{int(v):,}".replace(",", " ")


def _fmt_d(d):
    return f"{abs(d):,}".replace(",", " ") if d >= 0 else f"-{abs(d):,}".replace(",", " ")


def _kalit(nom):
    return _norm(nom)


def sarlavha_toruri(kod):
    """Sarlavha qatorlari: [[(matn, colspan, rowspan, tur)]] va ustunlar ro'yxati.

    Yo'lda bo'sh yorliq ("") - o'sha darajada katak chizilmaydi, ustidagi katak pastga cho'ziladi.
    """
    ust = _ustunlar_royxati(kod)
    D = max(len(u["yol"]) for u in ust)
    n = len(ust)
    hujayra = []  # (daraja, i, j, matn, rowspan, barg)
    for lvl in range(D):
        i = 0
        while i < n:
            yol = ust[i]["yol"]
            if lvl >= len(yol):
                i += 1
                continue
            pref = yol[: lvl + 1]
            j = i
            while j + 1 < n and len(ust[j + 1]["yol"]) > lvl and ust[j + 1]["yol"][: lvl + 1] == pref:
                j += 1
            barg = all(len(ust[k]["yol"]) == lvl + 1 for k in range(i, j + 1))
            hujayra.append({"lvl": lvl, "i": i, "j": j, "t": yol[lvl], "rs": (D - lvl) if barg else 1, "barg": barg})
            i = j + 1
    # bo'sh yorliqlarni olib tashlab, ustki katakni cho'zish
    for h in [x for x in hujayra if x["t"] == ""]:
        for p in hujayra:
            if p["lvl"] < h["lvl"] and p["i"] <= h["i"] and p["j"] >= h["j"] and p["t"] != "" and p["lvl"] == h["lvl"] - 1:
                p["rs"] += 1
                break
        else:  # ustki bo'sh bo'lsa, undan ham yuqoriga qidiramiz
            for p in sorted((x for x in hujayra if x["lvl"] < h["lvl"] and x["t"] != "" and x["i"] <= h["i"] and x["j"] >= h["j"]), key=lambda x: -x["lvl"]):
                p["rs"] += 1
                break
    qat = [[] for _ in range(D)]
    for h in hujayra:
        if h["t"] == "":
            continue
        qat[h["lvl"]].append((h["t"], h["j"] - h["i"] + 1, h["rs"], "barg" if h["barg"] else "guruh"))
    return qat, ust


def jadval(kod, bugun, baza=None):
    """Bir bet uchun tayyor jadval.

    bugun, baza: {kod: [qatorlar]} (baza None bo'lsa o'zgarishlar bo'sh). Qaytaradi:
    {"bosh": [[(matn, colspan, rowspan, tur)]], "ustunlar": [...], "qatorlar": [{"nom","jami","katak":[{...}]}]}
    """
    bosh_q, ust = sarlavha_toruri(kod)
    bosh = bosh_q
    bq = {}
    if baza and kod in baza:
        for r in baza[kod]:
            bq[_kalit(r["nom"])] = r
    qatorlar = []
    for r in bugun.get(kod, []):
        b = bq.get(_kalit(r["nom"]))
        katak = []
        for u in ust:
            if u["kind"] == "d":
                if baza is None or b is None:
                    katak.append({"d": None, "t": "", "cls": "", "kind": "d"})
                    continue
                k = u["base"]
                d = (r["v"].get(k) or 0) - (b["v"].get(k) or 0)
                if d == 0:
                    katak.append({"d": 0, "t": "", "cls": "", "kind": "d"})
                else:
                    katak.append({"d": d, "t": _fmt_d(d), "cls": "up" if d > 0 else "dn", "kind": "d"})
            else:
                v = r["v"].get(u["key"])
                t = _fmt(v, u["p"])
                if v is None and r["jami"]:
                    t = "-"
                katak.append({"v": v, "t": t, "kind": u["kind"], "rang": u.get("rang", "")})
        qatorlar.append({"nom": r["nom"], "jami": r["jami"], "katak": katak})
    return {"kod": kod, "bosh": bosh, "ustunlar": ust, "qatorlar": qatorlar,
            "sarlavha": SAHIFALAR[kod]["sarlavha"], "tur": SAHIFALAR[kod]["tur"], "nom": SAHIFALAR[kod]["nom"]}


def barcha_jadvallar(bugun, baza=None):
    return [jadval(k, bugun, baza) for k in SAHIFA_TARTIB if k in bugun]


# ------------------------------------------------------------------ ish kunlari
def standart_ish_kuni(d):
    return d.weekday() < 5


def ish_kuni_mi(d, belgilar):
    """belgilar: {date: True/False} - qo'lda belgilangan (True: ish kuni, False: dam olish)."""
    if d in belgilar:
        return belgilar[d]
    return standart_ish_kuni(d)
