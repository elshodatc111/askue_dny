"""Respublika dinamikasini Excel (har bet - alohida varaq) va PDF (asl PDF dagidek, to'liq lotin) ga eksport qilish."""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import resp as R
from .eksport import KOK, KOK_SARLAVHA, KREM, KULRANG, QIZIL, QORA, SARIQ, YASHIL, _bol, _kenglik, _lotin, _PDF, _sigdir

KOK_PDF = (0.0, 0.2, 0.9)
TO_Q_SARIQ = (0.85, 0.45, 0.0)
RANG_PDF = {"g": YASHIL, "r": QIZIL, "b": (0.1, 0.3, 0.8), "o": TO_Q_SARIQ, "": QORA}
RANG_XLSX = {"g": "00A651", "r": "C00000", "b": "1F4FD8", "o": "C55A11", "": "000000"}
SEPTSET = {"DINAMIKA": "D I N A M I K A", "MA'LUMOT": "M A ' L U M O T"}


def _sana(d):
    return d.strftime("%d.%m.%Y") if d else ""


def davr_matni(meta):
    if meta.get("baza"):
        return f"Dinamika: {_sana(meta['baza'])} - {_sana(meta['sana'])}"
    return f"Ma'lumot sanasi: {_sana(meta['sana'])}"


def fayl_nomi(meta, kengaytma):
    return f"Qashqadaryo_HETK_respublika_dinamika_{meta['sana']:%d.%m.%Y}.{kengaytma}"


def _yuklangan(meta):
    v = meta.get("yuklangan")
    return f"Ma'lumot yuklangan: {v:%d.%m.%Y %H:%M}" if v else ""


# ------------------------------------------------------------------ Excel
def _chegara():
    t = Side(style="thin", color="000000")
    return Border(left=t, right=t, top=t, bottom=t)


def xlsx(jadvallar, meta):
    wb = Workbook()
    wb.remove(wb.active)
    for i, j in enumerate(jadvallar, 1):
        ws = wb.create_sheet(f"{i}-{j['nom']}"[:31].replace("/", "-"))
        _varaq(ws, j, meta)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _varaq(ws, j, meta):
    ust, bosh, qat = j["ustunlar"], j["bosh"], j["qatorlar"]
    n = len(ust)
    D = len(bosh)
    jami_col = n + 1
    ch = _chegara()
    sar_fill = PatternFill("solid", fgColor="DCE6F1")
    sariq = PatternFill("solid", fgColor="FFF2CC")
    krem = PatternFill("solid", fgColor="FFFDE7")
    ws.sheet_view.showGridLines = False

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=jami_col)
    c = ws.cell(2, 1, j["sarlavha"])
    c.font = Font(bold=True, size=14)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=jami_col)
    c = ws.cell(3, 1, SEPTSET.get(j["tur"], j["tur"]))
    c.font = Font(bold=True, size=13, color="FF0000")
    c.alignment = Alignment(horizontal="center")
    ws.cell(5, 1, "Hudud nomi:").font = Font(size=10)
    ws.merge_cells(start_row=5, start_column=2, end_row=5, end_column=min(3, jami_col))
    c = ws.cell(5, 2, "Qashqadaryo HETK")
    c.font = Font(bold=True, color="1F4FD8")
    for cc in range(2, min(3, jami_col) + 1):
        ws.cell(5, cc).border = Border(left=Side(style="thin", color="1F4FD8") if cc == 2 else None, right=Side(style="thin", color="1F4FD8") if cc == min(3, jami_col) else None,
                                       top=Side(style="thin", color="1F4FD8"), bottom=Side(style="thin", color="1F4FD8"))
    ws.merge_cells(start_row=5, start_column=max(4, jami_col - 5), end_row=5, end_column=jami_col)
    c = ws.cell(5, max(4, jami_col - 5), davr_matni(meta))
    c.font = Font(bold=True, color="0000FF")
    c.alignment = Alignment(horizontal="right")

    h0 = 7  # sarlavha birinchi qatori
    # chap ustun
    ws.merge_cells(start_row=h0, start_column=1, end_row=h0 + D - 1, end_column=1)
    c = ws.cell(h0, 1, "Hudud nomi")
    c.font = Font(bold=True, size=11)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r in range(h0, h0 + D):
        ws.cell(r, 1).fill = sar_fill
        ws.cell(r, 1).border = ch
    # sarlavha katak-katak
    band = [[False] * (n + 2) for _ in range(D)]
    for r, qator in enumerate(bosh):
        col = 2
        for (t, cs, rs, tur) in qator:
            while col <= n + 1 and band[r][col]:
                col += 1
            for rr in range(r, r + rs):
                for cc in range(col, col + cs):
                    band[rr][cc] = True
            if cs > 1 or rs > 1:
                ws.merge_cells(start_row=h0 + r, start_column=col, end_row=h0 + r + rs - 1, end_column=col + cs - 1)
            c = ws.cell(h0 + r, col, t)
            kichik = t == "↑↓"
            c.font = Font(bold=True, size=8 if tur == "barg" and not kichik else 9, color="C00000" if t in ("soni", "%", "↑↓") else "1F2937")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for rr in range(r, r + rs):
                for cc in range(col, col + cs):
                    x = ws.cell(h0 + rr, cc)
                    x.fill = sar_fill
                    x.border = ch
            col += cs
    # ma'lumot
    r0 = h0 + D
    for ri, q in enumerate(qat):
        r = r0 + ri
        jami = q["jami"]
        c = ws.cell(r, 1, q["nom"])
        c.font = Font(bold=jami, size=9)
        c.alignment = Alignment(horizontal="center" if jami else "left", vertical="center")
        c.border = ch
        if jami:
            c.fill = sariq
        for ci, (u, k) in enumerate(zip(ust, q["katak"]), 2):
            x = ws.cell(r, ci)
            x.border = ch
            if jami:
                x.fill = sariq
            elif u["kind"] != "d" and u.get("rang"):
                pass
            if u["kind"] == "d":
                d = k.get("d")
                if d:
                    x.value = d
                    x.number_format = '[Red]"↑ "#,##0;[Blue]"↓ "-#,##0;;'
                    x.font = Font(bold=True, size=8)
                x.alignment = Alignment(horizontal="right", vertical="center")
            elif u["kind"] == "p":
                v = k.get("v")
                if v is not None:
                    x.value = v / 100.0
                    x.number_format = "0%" if float(v).is_integer() else "0.0%"
                x.font = Font(bold=jami, size=9, color=RANG_XLSX.get(u.get("rang", ""), "000000") if jami else "000000")
                x.alignment = Alignment(horizontal="center", vertical="center")
            else:
                v = k.get("v")
                if v is None:
                    if jami:
                        x.value = "-"
                else:
                    x.value = v
                    x.number_format = "#,##0" if float(v).is_integer() else "0.0"
                x.font = Font(bold=True, size=9, color=RANG_XLSX.get(u.get("rang", ""), "000000"))
                x.alignment = Alignment(horizontal="right", vertical="center")
        ws.row_dimensions[r].height = 18
    for r in range(h0, h0 + D):
        ws.row_dimensions[r].height = 24 if r < h0 + D - 1 else 20
    ws.row_dimensions[h0].height = 30
    yoz = r0 + len(qat) + 1
    ws.cell(yoz, 1, "Qashqadaryo HETK - Hodimlar nazorati. " + _yuklangan(meta)).font = Font(size=8, color="596273")
    # ustun kengliklari
    ws.column_dimensions["A"].width = 20
    for ci, u in enumerate(ust, 2):
        ws.column_dimensions[get_column_letter(ci)].width = 8.5 if u["kind"] == "d" else (10.5 if u["kind"] == "n" else 7.5)
    ws.freeze_panes = ws.cell(r0, 2)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True


# ------------------------------------------------------------------ PDF
# Asl respublika PDF sining dizayni (Letter albom, ustun chegaralari, ranglar) resp_shablon.json da saqlanadi
# (tools/shablon_yasa.py asl PDF dan yaratadi). Shriftlar: asl Calibri o'rniga Helvetica (biroz kichraytirilgan).
import json
import os

_SH = None
PW, PH = 792.0, 612.0
KICHRAY = 0.93
QATOR_B = 13.43
JAMI_B = 18.5
QAT0 = 254.7
HDR_FON = (0.867, 0.922, 0.969)
JAMI_FON = (1.0, 0.902, 0.6)
UP_STD = (1.0, 0.0, 0.0)
DN_STD = (0.0, 0.0, 1.0)
HUDUD_RANG = (0.0, 0.4, 1.0)


def _shablon():
    global _SH
    if _SH is None:
        with open(os.path.join(os.path.dirname(__file__), "resp_shablon.json"), encoding="utf-8") as f:
            _SH = json.load(f)
    return _SH


def pdf(jadvallar, meta):
    p = _PDF(PW, PH)
    sh = _shablon()
    for j in jadvallar:
        _bet(p, j, meta, sh[j["kod"]])
    return p.bytes()


def _c(v, std=None):
    return tuple(v) if v else std


def _sigdir_n(t, olcham, kenglik, qalin, eng_kichik=4.4):
    return _sigdir(t, olcham, kenglik, qalin, eng_kichik)


def _markaz_matn(p, x0, y0, x1, y1, t, olcham, qalin, rang, kursiv=False, tekis="c"):
    """Katak ichiga ko'p qatorli matn (markazlangan), sig'masa shrift kichrayadi."""
    w, h = x1 - x0, y1 - y0
    sz = olcham
    while True:
        satr = _bol(t, sz, w - 3.0, qalin)
        lh = sz * 1.13
        sozlar_ok = all(_kenglik(_lotin(so), sz, qalin) <= w - 3.0 for so in t.replace("\n", " ").split())
        if (len(satr) * lh <= h - 1.5 and sozlar_ok) or sz <= 4.2:
            break
        sz -= 0.2
    lh = sz * 1.13
    top = y0 + (h - len(satr) * lh) / 2
    for k, s_ in enumerate(satr):
        yb = top + k * lh + sz * 0.82
        p.matn(x0 + 1.5, yb, s_, sz, qalin, rang=rang, tekis=tekis, kenglik=w - 3.0, kursiv=kursiv)


def _aylantirilgan_matn(p, x0, y0, x1, y1, t, olcham, qalin, rang):
    """Tor ustun sarlavhasi: matn 90 daraja aylantirilgan (pastdan yuqoriga)."""
    w, h = x1 - x0, y1 - y0
    sz = olcham
    while True:
        satr = _bol(t, sz, h - 3.0, qalin)
        lh = sz * 1.12
        sozlar_ok = all(_kenglik(_lotin(so), sz, qalin) <= h - 3.0 for so in t.split())
        if (len(satr) * lh <= w - 1.0 and sozlar_ok) or sz <= 4.2:
            break
        sz -= 0.2
    lh = sz * 1.12
    left = x0 + (w - len(satr) * lh) / 2
    cy = (y0 + y1) / 2
    for k, s_ in enumerate(satr):
        tw = _kenglik(_lotin(s_), sz, qalin)
        p.matn_aylantirilgan(left + k * lh + sz * 0.8, cy + tw / 2, s_, sz, qalin, rang)


def _delta_chiz(p, x0, x1, yc, d, t, olcham, rang):
    tw = _kenglik(t, olcham, True)
    g = 6.6
    sx = x0 + ((x1 - x0) - (g + tw)) / 2
    p.strelka(sx + 2.8, yc, d > 0, rang, 6.0)
    p.matn(sx + g, yc + olcham * 0.34, t, olcham, True, rang=rang)


def _ustun_rang_d(col):
    """Delta ustun: o'sish va kamayish strelkasi ranglari (asl PDF dan)."""
    up = dn = None
    for k in ("d", "j"):
        st = col.get(k) or {}
        up = up or st.get("up")
        dn = dn or st.get("dn")
    up = tuple(up) if up else None
    dn = tuple(dn) if dn else None
    if up and not dn:
        dn = DN_STD if up == UP_STD else UP_STD
    if dn and not up:
        up = UP_STD if dn == DN_STD else DN_STD
    return up or UP_STD, dn or DN_STD


def _bet(p, j, meta, sh):
    p.yangi_sahifa()
    b = sh["bounds"]
    hy = sh["hy"]
    ust, bosh, qat = j["ustunlar"], j["bosh"], j["qatorlar"]
    n = len(ust)
    chap, ong = b[0], b[-1]
    markaz = PW / 2

    # ---- sarlavha, DINAMIKA/MA'LUMOT, hudud nomi, davr
    t = j["sarlavha"]
    fz = _sigdir(t, 12.4 * KICHRAY, ong - chap + 20, True, 8)
    p.matn(0, 119.5, t, fz, True, tekis="c", kenglik=PW)
    p.matn(0, 143.0, SEPTSET.get(j["tur"], j["tur"]), 12.4 * KICHRAY, True, rang=(1.0, 0.0, 0.0), tekis="c", kenglik=PW)
    p.matn(chap + 8.0, 156.3, "Hudud nomi:", 9.6 * KICHRAY)
    bx0, bx1 = sh["box"]
    p.rect(bx0, 145.3, bx1 - bx0, 14.8, chiziq=(0.0, 0.69, 0.941), qalinlik=0.9)
    p.matn(bx0 + 2.5, 156.3, "Qashqadaryo HETK", 9.6 * KICHRAY, True, rang=HUDUD_RANG)
    p.matn(ong - 330, 156.3, davr_matni(meta), 9.6 * KICHRAY, True, rang=DN_STD, tekis="r", kenglik=330)

    # ---- sarlavha: Hudud nomi katagi
    p.rect(chap, hy[0], b[1] - chap, hy[-1] - hy[0], tola=HDR_FON, chiziq=QORA, qalinlik=0.5)
    yc = (hy[0] + hy[-1]) / 2
    fn = 11.0 * KICHRAY
    p.matn(chap, yc - 1.5, "Hudud", fn, True, tekis="c", kenglik=b[1] - chap)
    p.matn(chap, yc + fn - 0.5, "nomi", fn, True, tekis="c", kenglik=b[1] - chap)

    # ---- sarlavha katakchalari
    gr = [[False] * (n + 1) for _ in bosh]
    for r, qator in enumerate(bosh):
        c = 0
        for k, (t_, cs, rs, tur) in enumerate(qator):
            while c < n and gr[r][c]:
                c += 1
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    gr[rr][cc] = True
            st = sh["hdr"][r][k]
            x0, x1 = b[c + 1], b[c + cs + 1]
            y0, y1 = hy[r], hy[r + rs]
            p.rect(x0, y0, x1 - x0, y1 - y0, tola=_c(st.get("fill"), HDR_FON), chiziq=QORA, qalinlik=0.5)
            rang = _c(st.get("color"), QORA)
            if rang == QORA and tur == "barg" and cs == 1 and t_ not in ("soni", "%", "↑↓"):
                dc = _c(((sh["cols"][c] or {}).get("d") or {}).get("color"))
                if dc and dc != QORA and dc != (0.0, 0.0, 1.0):
                    rang = dc
            sz = min(max(st.get("size", 7.0), 5.8), 9.6) * KICHRAY
            if t_ == "↑↓":
                cxm = (x0 + x1) / 2
                p.strelka(cxm - 3.4, (y0 + y1) / 2, True, _c(st.get("up"), (0.0, 0.4, 1.0)), 5.0)
                p.strelka(cxm + 3.4, (y0 + y1) / 2, False, _c(st.get("dn"), (1.0, 0.0, 0.0)), 5.0)
            elif st.get("rot"):
                _aylantirilgan_matn(p, x0, y0, x1, y1, t_, sz, st.get("bold", True), rang)
            else:
                _markaz_matn(p, x0, y0, x1, y1, t_, sz, st.get("bold", True), rang, kursiv=st.get("italic", False))
            c += cs

    # ---- ma'lumot qatorlari
    y = hy[-1]
    nom_st = sh.get("nom") or {}
    for q in qat:
        jami = q["jami"]
        rh = JAMI_B if jami else QATOR_B
        yc = y + rh / 2
        # nom katagi
        p.rect(chap, y, b[1] - chap, rh, tola=JAMI_FON if jami else None, chiziq=QORA, qalinlik=0.5)
        if jami:
            fn = _sigdir_n(q["nom"], 9.6 * KICHRAY, b[1] - chap - 6, True)
            p.matn(chap, yc + fn * 0.34, q["nom"], fn, True, tekis="c", kenglik=b[1] - chap)
        else:
            fn = _sigdir_n(q["nom"], 8.3 * KICHRAY, b[1] - chap - 12, False)
            p.matn(chap + 9.0, yc + fn * 0.34, q["nom"], fn, False)
        for ci, (u, k) in enumerate(zip(ust, q["katak"])):
            col = sh["cols"][ci]
            x0, x1 = b[ci + 2 - 1], b[ci + 2]
            if jami:
                fon = _c(col.get("jfill"), JAMI_FON)
            else:
                fon = _c(col.get("fill"))
            p.rect(x0, y, x1 - x0, rh, tola=fon, chiziq=QORA, qalinlik=0.5)
            if u["kind"] == "d":
                d = k.get("d")
                if d:
                    up, dn = _ustun_rang_d(col)
                    _delta_chiz(p, x0, x1, yc, d, k["t"], 7.2 if not jami else 7.6, up if d > 0 else dn)
            else:
                t_ = k.get("t", "")
                if t_:
                    st = (col.get("j") if jami else col.get("d")) or {}
                    rang = _c(st.get("color"), QORA)
                    bold = True if jami else st.get("bold", True)
                    base = 9.6 if jami else 8.3
                    fs = _sigdir_n(t_, base * KICHRAY, x1 - x0 - 5, bold)
                    p.matn(x0, yc + fs * 0.34, t_, fs, bold, rang=rang, tekis="r", kenglik=x1 - x0 - 4.2)
        y += rh
