"""Matnni normallashtirish, TP kaliti va mas'ul hodimlar satrini ajratish."""
import hashlib
import re

_APOS = str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'", "´": "'"})
# Kirillcha va lotincha o'xshash harflar bir xil bo'lishi uchun (faqat kalit uchun)
_LOOK = str.maketrans(
    {
        "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
        "а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x",
    }
)

ORDER_KEYS = [
    "baxoriston", "guzor", "dehqonobod", "qamashi", "qarshi sh", "qarshi t", "koson", "kasbi", "kitob",
    "mirishkor", "muborak", "nishon", "chiroqchi", "shahrisabz sh", "shahrisabz t", "yakkabog", "kokdala",
]


def sozlash(v):
    """Hujayra qiymatini toza matnga aylantiradi."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return re.sub(r"\s+", " ", str(v)).strip()


def norm(s):
    s = "" if s is None else str(s)
    s = s.translate(_APOS).translate(_LOOK)
    return re.sub(r"\s+", " ", s).strip().lower()


def tr_norm(s):
    n = norm(s)
    return n.lstrip("0") or n


def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def tp_kalit(tuman, podst, feeder, tr):
    return sha("|".join([norm(tuman), norm(podst), norm(feeder), tr_norm(tr)]))


def mas_kalit(s):
    return sha(norm(s))


def qisqa_nom(nom):
    n = re.sub(r"\s+", " ", nom or "").strip()
    n = re.sub(r"\s+ShETK$", " sh.", n)
    n = re.sub(r"\s+TETK$", " t.", n)
    return n


def tuman_tartibi(nom):
    n = norm(nom).replace("'", "")
    n = n.replace(" shetk", " sh").replace(" tetk", " t")
    for i, k in enumerate(ORDER_KEYS):
        if n.startswith(k):
            return i + 1
    return 100


_SUFFIX = {"o'g'li", "ug'li", "ugli", "ogli", "o'gli", "qizi", "kizi", "o'g'lu"}


def hodimlarni_ajrat(raw):
    """'Haitov.SH Ashurova.M Qurbonova.D' kabi satrdan alohida hodim ismlarini ajratadi."""
    if not raw:
        return []
    s = re.sub(r"\s+", " ", str(raw)).strip()
    s = re.sub(r"\s*\.\s+", ", ", s)  # ". " yoki " . "
    s = re.sub(r"\s+\.(?=\S)", ", ", s)  # " .FAMILIYA"
    s = re.sub(r"\.+$", "", s)
    parts = [p.strip(" ,;.") for p in re.split(r"[;,]+", s)]
    parts = [p for p in parts if p]
    out = []
    for p in parts:
        toks = p.split(" ")
        if len(toks) > 1 and all(re.fullmatch(r"[^\s.]+\.[^\s.]{1,4}", t) for t in toks):
            out.extend(toks)  # Familiya.I Familiya.I ...
        else:
            out.append(p)
    if len(out) == 1:
        w = out[0].split(" ")
        low = [x.lower().translate(_APOS) for x in w]
        if len(w) >= 4 and len(w) % 2 == 0 and not any(x in _SUFFIX for x in low) and all("." not in x for x in w):
            out = [" ".join(w[i : i + 2]) for i in range(0, len(w), 2)]
    return out


def pinflar(raw):
    return re.findall(r"\d{9,14}", raw or "")
