"""Asl respublika PDF dan dizayn shablonini (chegaralar, ranglar, shriftlar) olib JSON ga yozadi."""
import os, sys, json, collections, statistics
os.environ["DB_ENGINE"] = "sqlite"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/mnt/user-data/outputs/hodimlar")
import django; django.setup()
import pdfplumber
from core.services import resp as R

SRC = "/mnt/user-data/uploads/5dc49dbb-12.11.2026.pdf"
BETLAR = {"r1": 0, "r2": 1, "r3": 2, "r4": 3, "r6": 5, "r7": 6, "r8": 7}
HY = {"r1": [165.7, 187.8, 221.4, 236.2], "r2": [165.7, 187.8, 198.2, 221.4, 236.2],
      "r3": [165.7, 187.8, 198.2, 221.4, 236.2], "r4": [165.7, 187.8, 198.2, 221.4, 236.2],
      "r6": [165.7, 187.8, 198.2, 236.2], "r7": [165.7, 198.2, 221.4, 236.2], "r8": [165.7, 187.8, 221.4, 236.2]}
JAMI_Y = (236.2, 254.7)
ROW0, PITCH = 254.7, 13.43


def rnd(c):
    if c is None or isinstance(c, str): return None
    if isinstance(c, (int, float)): c = (c, c, c)
    c = tuple(c)
    if any(isinstance(v, str) for v in c): return None
    if len(c) == 1: c = (c[0],) * 3
    if len(c) == 4:  # cmyk
        k = c[3]; c = tuple((1 - v) * (1 - k) for v in c[:3])
    return [round(float(v), 3) for v in c[:3]]


def oq(c):
    r = rnd(c)
    return r is not None and tuple(r) == (1.0, 1.0, 1.0)


def bounds(pg, ymid=290.0):
    e = set()
    for r in pg.rects + pg.lines:
        if r["top"] <= ymid <= r["bottom"]:
            e.add(round(r["x0"])); e.add(round(r["x1"]))
    m = []
    for x in sorted(e):
        if m and x - m[-1] < 4: continue
        m.append(float(x))
    return m


def fill_at(pg, x, y):
    f = None
    for r in pg.rects:
        if r["x0"] - 0.3 <= x <= r["x1"] + 0.3 and r["top"] - 0.3 <= y <= r["bottom"] + 0.3 and r["fill"]:
            if r["x1"] - r["x0"] < 3 or r["bottom"] - r["top"] < 3: continue
            c = rnd(r["non_stroking_color"])
            if c is None or c == [0.0, 0.0, 0.0]: continue
            f = c
    return f


def chars_in(pg, x0, x1, y0, y1):
    out = []
    for c in pg.chars:
        cx = (c["x0"] + c["x1"]) / 2; cy = (c["top"] + c["bottom"]) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1 and c["text"].strip() and not oq(c["non_stroking_color"]) and c["size"] > 3.5:
            out.append(c)
    return out


def stil(cs, arrows=False):
    if not cs: return None
    txt = [c for c in cs if c["text"] not in "↑↓"]
    base = txt or cs
    col = collections.Counter(tuple(rnd(c["non_stroking_color"]) or (0, 0, 0)) for c in base).most_common(1)[0][0]
    rot = sum(abs(c["matrix"][1]) > abs(c["matrix"][0]) for c in base) > len(base) / 2
    sz = statistics.median(((c["x1"] - c["x0"]) / 1.2) if rot else c["size"] for c in base)
    d = {"color": list(col), "size": round(sz, 1),
         "bold": sum("Bold" in c["fontname"] for c in base) > len(base) / 2,
         "italic": any("Italic" in c["fontname"] for c in base),
         "rot": rot}
    up = [c for c in cs if c["text"] == "↑"]; dn = [c for c in cs if c["text"] == "↓"]
    if up: d["up"] = list(collections.Counter(tuple(rnd(c["non_stroking_color"]) or (0, 0, 0)) for c in up).most_common(1)[0][0])
    if dn: d["dn"] = list(collections.Counter(tuple(rnd(c["non_stroking_color"]) or (0, 0, 0)) for c in dn).most_common(1)[0][0])
    return d


pdf = pdfplumber.open(SRC)
out = {}
for kod, bi in BETLAR.items():
    pg = pdf.pages[bi]
    b = bounds(pg)
    if kod == "r8":
        b = [x for x in b if x != 130.0]
    rows, ust = R.sarlavha_toruri(kod)
    n = len(ust)
    assert len(b) - 1 == n + 1, (kod, len(b) - 1, n + 1)
    hy = HY[kod]; assert len(hy) - 1 == len(rows), kod
    S = {"bounds": b, "hy": hy, "cols": [], "hdr": []}
    # nom ustuni
    ncs = chars_in(pg, b[0], b[1], ROW0 + 1, ROW0 + 12 * PITCH)
    S["nom"] = stil(ncs)
    S["nom_fill"] = fill_at(pg, (b[0] + b[1]) / 2, ROW0 + 6)
    jn = chars_in(pg, b[0], b[1], JAMI_Y[0] + 1, JAMI_Y[1] - 1)
    S["jnom"] = stil(jn); S["jnom_fill"] = fill_at(pg, (b[0] + b[1]) / 2, 245)
    for i in range(n):
        x0, x1 = b[i + 1], b[i + 2]
        cs = chars_in(pg, x0, x1, ROW0 + 1, ROW0 + 17 * PITCH)
        js = chars_in(pg, x0, x1, JAMI_Y[0] + 1, JAMI_Y[1] - 1)
        fl = collections.Counter()
        for k in range(0, 14):
            f = fill_at(pg, (x0 + x1) / 2, ROW0 + k * PITCH + 6)
            fl[tuple(f) if f else None] += 1
        f = fl.most_common(1)[0][0]
        S["cols"].append({"d": stil(cs), "j": stil(js), "fill": list(f) if f else None,
                          "jfill": fill_at(pg, (x0 + x1) / 2, 245)})
    # header katakchalari
    ycol = lambda r: hy[r]
    col = 0
    gr = [[False] * (n + 1) for _ in rows]
    for r, qator in enumerate(rows):
        L = []
        c = 0
        for (t, cs_, rs, tur) in qator:
            while c < n and gr[r][c]: c += 1
            for rr in range(r, r + rs):
                for cc in range(c, c + cs_): gr[rr][cc] = True
            x0, x1 = b[c + 1], b[c + cs_ + 1]
            y0, y1 = hy[r], hy[r + rs]
            ch = chars_in(pg, x0, x1, y0, y1)
            # yacheyka tashqarisidagi (katta) matnlarni olib tashlamaymiz; faqat markaziga tushganlar
            st = stil(ch) or {"color": [0, 0, 0], "size": 7.0, "bold": True, "italic": False, "rot": False}
            st["fill"] = fill_at(pg, (x0 + x1) / 2, (y0 + y1) / 2) or [0.867, 0.922, 0.969]
            L.append(st)
            c += cs_
        S["hdr"].append(L)
    # hudud nomi katagi
    bx = [r for r in pg.rects if 144 < r["top"] < 147 and r["x1"] - r["x0"] > 40]
    S["box"] = [round(min(r["x0"] for r in bx), 1), round(max(r["x1"] for r in bx), 1)] if bx else [b[1], b[1] + 100]
    S["hnom"] = stil(chars_in(pg, b[0], b[1], 166, 236))
    out[kod] = S
    print(kod, "ok", S["box"], S["nom"] and S["nom"]["size"], [c["d"] and c["d"]["color"] for c in S["cols"]][:5])
json.dump(out, open("/tmp/proto/resp_shablon.json", "w"), indent=0)
