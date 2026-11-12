"""Dinamika jadvalini Excel va PDF ga eksport qilish (namuna jadval dizaynida).

Namuna: markazda qalin sarlavha, qizil harf oralatilgan "D I N A M I K A", chapda "Hudud nomi" (ramkali), o'ngda
ko'k "Dinamika: sana - sana"; jadval qora ingichka chiziqli, sarlavha och ko'k, "Jami" qatori sariq,
o'zgarishlar strelkalar bilan (qizil - yomonlashgan, yashil - yaxshilangan).

PDF qo'shimcha kutubxonasiz (sof Python) yaratiladi: standart Helvetica shrifti, A4 gorizontal. Standart shriftda o'zbek
lotin harflaridagi ʻ belgisi yo'q, shuning uchun PDF da oddiy apostrof ishlatiladi; strelkalar chiziq bilan chiziladi.
"""
import datetime
import io

from django.http import HttpResponse

from . import stats as S

# Helvetica harf kengliklari (1000 birlik = 1 em), cp1252 kodlari 32..255
_WR = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 761, 556, 761, 222, 556, 333, 1000, 556, 556, 333, 1000, 667, 333, 1000, 761, 611, 761, 761, 222, 222, 333, 333, 350, 556, 1000, 333, 1000, 500, 333, 944, 761, 500, 667, 278, 333, 556, 556, 556, 556, 260, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 556, 537, 278, 333, 333, 365, 556, 834, 834, 834, 611, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 584, 611, 556, 556, 556, 556, 500, 556, 500]
_WB = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 761, 556, 761, 278, 556, 500, 1000, 556, 556, 333, 1000, 667, 333, 1000, 761, 611, 761, 761, 278, 278, 500, 500, 350, 556, 1000, 333, 1000, 556, 333, 944, 761, 500, 667, 278, 333, 556, 556, 556, 556, 280, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 611, 556, 278, 333, 333, 365, 556, 834, 834, 834, 611, 722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278, 611, 611, 611, 611, 611, 611, 611, 584, 611, 611, 611, 611, 611, 556, 611, 556]

_BELGI = {
    "ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'", "´": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
    "›": ">", "«": '"', "»": '"', "№": "N",
}

# ranglar
KOK_SARLAVHA = (0.863, 0.902, 0.945)   # DCE6F1
SARIQ = (1.0, 0.949, 0.8)              # FFF2CC
KREM = (1.0, 0.992, 0.906)             # FFFDE7
QORA = (0, 0, 0)
QIZIL = (0.85, 0.0, 0.0)
YASHIL = (0.0, 0.6, 0.2)
KOK = (0.0, 0.2, 0.9)
KULRANG = (0.35, 0.4, 0.5)


def _lotin(t):
    t = str(t)
    for k, v in _BELGI.items():
        t = t.replace(k, v)
    return t.encode("cp1252", errors="replace").decode("cp1252")


def _kenglik(t, olcham, qalin=False):
    tab = _WB if qalin else _WR
    w = 0
    for ch in t:
        try:
            b = ch.encode("cp1252")[0]
        except UnicodeEncodeError:
            b = 63
        w += tab[b - 32] if 32 <= b <= 255 else 500
    return w * olcham / 1000.0


def _bol(t, olcham, kenglik, qalin=False):
    """Matnni berilgan kenglikda qatorlarga bo'ladi."""
    t = _lotin(t)
    qatorlar = []
    for abzats in t.split("\n"):
        joriy = ""
        for so in abzats.split(" "):
            sinov = so if not joriy else joriy + " " + so
            if _kenglik(sinov, olcham, qalin) <= kenglik:
                joriy = sinov
            else:
                if joriy:
                    qatorlar.append(joriy)
                while _kenglik(so, olcham, qalin) > kenglik and len(so) > 1:
                    k = len(so)
                    while k > 1 and _kenglik(so[:k], olcham, qalin) > kenglik:
                        k -= 1
                    qatorlar.append(so[:k])
                    so = so[k:]
                joriy = so
        qatorlar.append(joriy)
    return qatorlar or [""]


def _esc(t):
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class _PDF:
    """Juda sodda PDF yozuvchi: matn, to'rtburchak, chiziq, strelka."""

    def __init__(self, w=842.0, h=595.0):
        self.w, self.h = w, h
        self.sahifalar = []
        self.joriy = None

    def yangi_sahifa(self):
        self.joriy = []
        self.sahifalar.append(self.joriy)

    def rect(self, x, y, w, h, tola=None, chiziq=None, qalinlik=0.5):
        """y - sahifa tepasidan pastga qarab."""
        yy = self.h - y - h
        c = []
        if tola:
            c.append("%.3f %.3f %.3f rg" % tola)
        if chiziq:
            c.append("%.3f %.3f %.3f RG %.2f w" % (chiziq + (qalinlik,)))
        op = "B" if (tola and chiziq) else "f" if tola else "S"
        c.append("%.2f %.2f %.2f %.2f re %s" % (x, yy, w, h, op))
        self.joriy.append("\n".join(c))

    def chiziq(self, x1, y1, x2, y2, rang=QORA, qalinlik=0.5):
        self.joriy.append("%.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S" % (rang + (qalinlik, x1, self.h - y1, x2, self.h - y2)))

    def strelka(self, cx, cy, yuqori, rang, olcham=5.0):
        """Kichik strelka (yuqoriga yoki pastga). cy - markaz (sahifa tepasidan)."""
        h = olcham
        y = self.h - cy
        s = 1 if yuqori else -1
        qb = "%.3f %.3f %.3f" % rang
        self.joriy.append(
            f"{qb} RG {qb} rg 0.7 w {cx:.2f} {y - s * h * 0.5:.2f} m {cx:.2f} {y + s * h * 0.35:.2f} l S "
            f"{cx - h * 0.38:.2f} {y + s * h * 0.05:.2f} m {cx + h * 0.38:.2f} {y + s * h * 0.05:.2f} l {cx:.2f} {y + s * h * 0.6:.2f} l f")

    def matn(self, x, y, t, olcham=8, qalin=False, rang=QORA, tekis="l", kenglik=0, kursiv=False):
        """y - qator asosi. tekis: l/c/r (kenglik berilganda)."""
        t = _lotin(t)
        if kenglik and tekis != "l":
            tw = _kenglik(t, olcham, qalin)
            x = x + (kenglik - tw) / 2 if tekis == "c" else x + kenglik - tw
        self.joriy.append("BT /%s %.2f Tf %.3f %.3f %.3f rg %.2f %.2f Td (%s) Tj ET" % (
            "F3" if (kursiv and qalin) else "F2" if qalin else "F1", olcham, rang[0], rang[1], rang[2], x, self.h - y, _esc(t)))

    def matn_aylantirilgan(self, x, y, t, olcham=7, qalin=True, rang=QORA):
        """Vertikal (90 daraja) matn: (x, y) - matn boshi (pastki nuqta), tepaga qarab yoziladi."""
        t = _lotin(t)
        self.joriy.append("BT /%s %.2f Tf %.3f %.3f %.3f rg 0 1 -1 0 %.2f %.2f Tm (%s) Tj ET" % (
            "F2" if qalin else "F1", olcham, rang[0], rang[1], rang[2], x, self.h - y, _esc(t)))

    def bytes(self):
        obj = []

        def add(b):
            obj.append(b)
            return len(obj)

        kat = add(None)
        sah_root = add(None)
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        f3 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-BoldOblique /Encoding /WinAnsiEncoding >>")
        sah_idlar = []
        for s in self.sahifalar:
            data = ("\n".join(s)).encode("cp1252", errors="replace")
            c = add(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
            sid = add(None)
            obj[sid - 1] = ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.0f %.0f] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R /F3 %d 0 R >> >> /Contents %d 0 R >>" % (
                sah_root, self.w, self.h, f1, f2, f3, c)).encode()
            sah_idlar.append(sid)
        obj[kat - 1] = ("<< /Type /Catalog /Pages %d 0 R >>" % sah_root).encode()
        obj[sah_root - 1] = ("<< /Type /Pages /Count %d /Kids [%s] >>" % (len(sah_idlar), " ".join("%d 0 R" % i for i in sah_idlar))).encode()
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n")
        ofs = []
        for i, o in enumerate(obj, 1):
            ofs.append(out.tell())
            out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
        x = out.tell()
        out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(obj) + 1))
        for o in ofs:
            out.write(b"%010d 00000 n \n" % o)
        out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(obj) + 1, kat, x))
        return out.getvalue()


# ------------------------------------------------------------------ umumiy
def _sana(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _hudud(meta):
    return meta.get("tuman") or "Qashqadaryo HETK"


def _sarlavha(meta):
    hudud = meta.get("tuman") or "Qashqadaryo HETK"
    return f"{hudud} hududida {S.EKSPORT_SARLAVHA[meta['tur']]}"


def _davr(meta):
    if meta.get("a"):
        d1, d2 = sorted([meta["a"], meta["b"]])
        return f"Dinamika: {_sana(d1)} - {_sana(d2)}"
    return f"Ma'lumot sanasi: {_sana(meta['b'])}"


def _fayl_nomi(meta, kengaytma):
    return f"dinamika_{meta['tur']}_{meta['b']:%Y-%m-%d}.{kengaytma}"


def _d(dt):
    """'↑ 3' / '↓ 39' -> ('+', '3') / ('-', '-39')"""
    if not dt:
        return None, ""
    if dt.startswith("↑"):
        return "up", dt[1:].strip()
    return "down", "-" + dt[1:].strip()


def _rang_xlsx(cls):
    return {"yomon": "FFD00000", "yaxshi": "FF00992E"}.get(cls, "FF1F3FE0")


def _rang_pdf(cls):
    return {"yomon": QIZIL, "yaxshi": YASHIL}.get(cls, KOK)


def _ustun_rang(key):
    """Raqam rangi: online - yashil, offline va uning bo'laklari - qizil, qolganlar - qora."""
    if key == "online":
        return "green"
    if key in ("offline", "k3", "k30"):
        return "red"
    return "black"


def _guruh_indekslari(jadval):
    if jadval.get("guruh_idx"):
        return jadval["guruh_idx"]
    kalitlar = [u[0] for u in jadval["ustunlar"]]
    out = []
    for nom, ks in jadval["guruhlar"]:
        idx = [kalitlar.index(k) for k in ks if k in kalitlar]
        if idx:
            out.append((nom, idx))
    return out


def _ustun_nomi(u):
    return u[1]


# ------------------------------------------------------------------ Excel
def dinamika_xlsx(jadval, meta):
    return kopchilik_xlsx([(jadval, meta)], _fayl_nomi(meta, "xlsx"))


def kopchilik_xlsx(elementlar, fayl):
    """Har bir jadval alohida varaqda (jadval, meta)."""
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for jadval, meta in elementlar:
        ws = wb.create_sheet({"p1": "Konsentrator va GPRS", "p2": "Aloqasiz va Primichka"}.get(meta["tur"], meta["tur"]))
        _xlsx_varaq(ws, jadval, meta)
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{fayl}"'
    wb.save(resp)
    return resp


def _xlsx_varaq(ws, jadval, meta):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    tuman = bool(meta.get("tuman"))
    ust = jadval["ustunlar"]
    boshi = 2 if tuman else 1
    jami_ustun = boshi + 2 * len(ust)
    qora = Side(style="thin", color="FF000000")
    chegara = Border(left=qora, right=qora, top=qora, bottom=qora)
    f_sarlavha = PatternFill("solid", fgColor="FFDCE6F1")
    f_jami = PatternFill("solid", fgColor="FFFFF2CC")
    f_krem = PatternFill("solid", fgColor="FFFFFDE7")
    shrift = "Calibri"

    # --- sarlavha qismi (namunadagidek)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=jami_ustun)
    c = ws.cell(2, 1, _sarlavha(meta))
    c.font = Font(name=shrift, bold=True, size=13)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=jami_ustun)
    c = ws.cell(4, 1, "D I N A M I K A" if meta.get("a") else "M A ' L U M O T")
    c.font = Font(name=shrift, bold=True, size=15, color="FFFF0000")
    c.alignment = Alignment(horizontal="center", vertical="center")
    if _yuklangan_matni(meta):
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=jami_ustun)
        yk = ws.cell(3, 1, _yuklangan_matni(meta))
        yk.font = Font(name=shrift, size=9, italic=True, color="FF666666")
        yk.alignment = Alignment(horizontal="center")
    ws.cell(6, 1, "Hudud nomi:").font = Font(name=shrift, size=11)
    ws.cell(6, 1).alignment = Alignment(horizontal="right")
    ws.merge_cells(start_row=6, start_column=2, end_row=6, end_column=min(jami_ustun, 4))
    nom_katagi = ws.cell(6, 2, _hudud(meta))
    nom_katagi.font = Font(name=shrift, bold=True, size=11, color="FF0070C0")
    nom_katagi.alignment = Alignment(horizontal="center")
    ko = Side(style="thin", color="FF00B0F0")
    for col in range(2, min(jami_ustun, 4) + 1):
        ws.cell(6, col).border = Border(top=ko, bottom=ko, left=ko if col == 2 else None, right=ko if col == min(jami_ustun, 4) else None)
    ws.merge_cells(start_row=6, start_column=max(jami_ustun - 5, 5), end_row=6, end_column=jami_ustun)
    c = ws.cell(6, max(jami_ustun - 5, 5), _davr(meta))
    c.font = Font(name=shrift, bold=True, size=11, color="FF0000FF")
    c.alignment = Alignment(horizontal="right")

    # --- jadval sarlavhasi: 3 qator
    h1, h2, h3 = 8, 9, 10
    guruhlar = _guruh_indekslari(jadval)
    ws.cell(h1, 1, "Brigada" if tuman else "Hudud nomi")
    ws.merge_cells(start_row=h1, start_column=1, end_row=h3, end_column=1)
    if tuman:
        ws.cell(h1, 2, "Biriktirilgan hodimlar")
        ws.merge_cells(start_row=h1, start_column=2, end_row=h3, end_column=2)
    for nom, idx in guruhlar:
        c0 = boshi + 1 + 2 * idx[0]
        c1 = boshi + 2 * idx[-1] + 2
        ws.cell(h1, c0, nom)
        ws.merge_cells(start_row=h1, start_column=c0, end_row=h1, end_column=c1)
    for i, u in enumerate(ust):
        c0 = boshi + 1 + 2 * i
        t = _ustun_nomi(u) + (f"\n({u[3]})" if len(u) > 3 and u[3] else "")
        ws.cell(h2, c0, t)
        ws.merge_cells(start_row=h2, start_column=c0, end_row=h2, end_column=c0 + 1)
        ws.cell(h3, c0, "soni")
        ws.cell(h3, c0 + 1, "↑ ↓")
    for r in (h1, h2, h3):
        for col in range(1, jami_ustun + 1):
            x = ws.cell(r, col)
            x.fill = f_sarlavha
            x.border = chegara
            x.font = Font(name=shrift, bold=True, size=11 if r == h1 else 10, color="FF000000")
            x.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for col in range(1, boshi + 1):
        ws.cell(h1, col).font = Font(name=shrift, bold=True, size=13)
    for i in range(len(ust)):
        c0 = boshi + 1 + 2 * i
        ws.cell(h3, c0).font = Font(name=shrift, bold=True, size=9, color="FFD00000")
        ws.cell(h3, c0 + 1).font = Font(name=shrift, bold=True, size=9, color="FF1F3FE0")
    ws.row_dimensions[h1].height = 22
    ws.row_dimensions[h2].height = 42
    ws.row_dimensions[h3].height = 16

    muddat_ustunlari = {i for _n, idx in guruhlar[1:] for i in idx} if len(guruhlar) > 1 and not jadval.get("birlashgan") else set()

    def yoz(r, nom, hodimlar, katak, jami=False):
        ws.cell(r, 1, nom)
        if tuman:
            ws.cell(r, 2, ", ".join(hodimlar) if hodimlar else "")
        for i, c in enumerate(katak):
            col = boshi + 1 + 2 * i
            son = ws.cell(r, col, c["v"] if c["v"] is not None else "-")
            son.number_format = "#,##0"
            r_ = _ustun_rang(ust[i][0])
            rang = {"green": "FF00A050", "red": "FFD00000", "black": "FF000000"}[r_]
            son.font = Font(name=shrift, bold=True, size=10, color=rang)
            son.alignment = Alignment(horizontal="right", vertical="center")
            yon, matn = _d(c["dt"])
            d = ws.cell(r, col + 1, ("↑ " if yon == "up" else "↓ ") + matn if yon else "")
            d.alignment = Alignment(horizontal="right", vertical="center")
            d.font = Font(name=shrift, bold=True, size=9, color=_rang_xlsx(c["cls"]))
            if jami:
                son.fill = f_jami
                d.fill = f_jami
            elif i in muddat_ustunlari:
                son.fill = f_krem
                d.fill = f_krem
        for col in range(1, jami_ustun + 1):
            x = ws.cell(r, col)
            x.border = chegara
            if col <= boshi:
                x.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center" if jami else "left")
                x.font = Font(name=shrift, bold=jami, size=11 if jami else 10)
                if jami:
                    x.fill = f_jami

    r = h3 + 1
    yoz(r, "Jami", [], jadval["jami"]["katak"], jami=True)
    for q in jadval["qatorlar"]:
        r += 1
        yoz(r, q["nom"], q.get("hodimlar"), q["katak"])
        if q.get("hodimlar"):
            ws.row_dimensions[r].height = max(15, 15 * (1 + len(", ".join(q["hodimlar"])) // 40))

    ws.column_dimensions["A"].width = 18
    if tuman:
        ws.column_dimensions["B"].width = 40
    for i in range(len(ust)):
        col = boshi + 1 + 2 * i
        ws.column_dimensions[get_column_letter(col)].width = 11
        ws.column_dimensions[get_column_letter(col + 1)].width = 8.5
    ws.freeze_panes = ws.cell(h3 + 1, boshi + 1)
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{h1}:{h3}"


# ------------------------------------------------------------------ PDF
def dinamika_pdf(jadval, meta):
    pdf = _PDF(792.0, 612.0)
    _chiz_pdf(pdf, jadval, meta)
    resp = HttpResponse(pdf.bytes(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{_fayl_nomi(meta, "pdf")}"'
    return resp


def kopchilik_pdf(elementlar):
    """Bir nechta dinamika jadvalini (jadval, meta) bitta PDF fayliga yig'adi; baytlar qaytaradi."""
    pdf = _PDF(792.0, 612.0)
    for jadval, meta in elementlar:
        _chiz_pdf(pdf, jadval, meta)
    return pdf.bytes()


def _sigdir(t, olcham, kenglik, qalin=True, eng_kichik=5.0):
    """Matn bitta qatorda sig'maguncha shriftni kamaytiradi."""
    t = _lotin(t)
    while olcham > eng_kichik and _kenglik(t, olcham, qalin) > kenglik:
        olcham -= 0.3
    return olcham


def _yuklangan_matni(meta):
    v = meta.get("yuklangan")
    return f"Ma'lumot yuklangan: {v:%d.%m.%Y %H:%M}" if v else ""


# Asl respublika PDF dizayni: Letter albom, ochiq-ko'k sarlavha, sariq "Jami", krem ustunlar, yupqa chiziqlar
PW, PH = 792.0, 612.0
_KICH = 0.93
_QB, _JB = 13.43, 18.5
_HDR = (0.867, 0.922, 0.969)
_JAMI = (1.0, 0.902, 0.6)
_CREAM = (1.0, 0.992, 0.937)
_QIZ = (0.753, 0.0, 0.0)
_YASH = (0.0, 0.69, 0.314)
_UP, _DN = (0.0, 0.4, 1.0), (1.0, 0.0, 0.0)
_KULR = (0.4, 0.4, 0.45)


def _d_rang(cls):
    return {"yomon": (1.0, 0.0, 0.0), "yaxshi": _YASH}.get(cls, (0.0, 0.0, 1.0))


def _v_rang(key):
    return {"green": _YASH, "red": _QIZ, "black": QORA}[_ustun_rang(key)]


def _chiz_pdf(pdf, jadval, meta):
    """Dinamika jadvali asl respublika PDF dagidek ko'rinishda chiziladi (ustun kengliklari matnga qarab hisoblanadi)."""
    tuman = bool(meta.get("tuman"))
    ust = jadval["ustunlar"]
    n = len(ust)
    guruhlar = _guruh_indekslari(jadval)
    muddat = {i for _n, idx in guruhlar[1:] for i in idx} if len(guruhlar) > 1 and not jadval.get("birlashgan") else set()
    if jadval.get("birlashgan") and len(guruhlar) > 1:
        muddat = {i for _n, idx in guruhlar[1:] for i in idx}
    keng = n > 10
    chap, ong = (24.0, 768.0) if keng else (36.0, 756.0)
    nom_w = 80.0 if keng else 92.0
    hod_w = 104.0 if tuman else 0.0
    qatorlar = [(jadval["jami"]["nom"], [], jadval["jami"]["katak"], True)] + [(q["nom"], q.get("hodimlar"), q["katak"], False) for q in jadval["qatorlar"]]

    def hisobla(fs):
        OL = 8.3 * _KICH * fs
        DL = 7.2 * fs
        cw = []
        for i in range(n):
            wv, wd = 22.0 * fs, 18.0 * fs
            for _n, _h, katak, _j in qatorlar:
                c = katak[i]
                wv = max(wv, _kenglik(_lotin(c["vt"] if c["v"] is not None else "-"), OL + (1 if _j else 0), True) + 7)
                yon, mt = _d(c["dt"])
                if yon:
                    wd = max(wd, _kenglik(_lotin(mt), DL, True) + 12)
            ws = max([_kenglik(_lotin(w_), OL - 0.6, True) for w_ in ust[i][1].split()] or [0]) + 4
            if wv + wd < ws:
                wd += ws - wv - wd
            cw.append([wv, wd])
        kerak = sum(a + b for a, b in cw)
        mavjud = ong - chap - nom_w - hod_w
        return OL, DL, cw, kerak, mavjud

    fs = 1.0
    for fs in (1.0, 0.94, 0.88, 0.82, 0.76, 0.7, 0.64):
        OL, DL, cw, kerak, mavjud = hisobla(fs)
        if kerak <= mavjud:
            break
    ON = 8.3 * _KICH * min(1.0, fs + 0.12)
    k = mavjud / kerak
    cw = [(a * k, b * k) for a, b in cw]
    xs = []
    x_ = chap + nom_w + hod_w
    for a, b in cw:
        xs.append(x_)
        x_ += a + b

    # sarlavha balandliklari
    g_h = 22.1
    u_qat = []
    for i, u in enumerate(ust):
        w = cw[i][0] + cw[i][1] - 4
        nom_q = _bol(u[1], OL - 0.4, w, True)
        hint = u[3] if len(u) > 3 and u[3] else ""
        h_q = _bol(hint, 6.3, w, False) if hint else []
        u_qat.append((nom_q, h_q))
    b2 = max(33.6, max(len(a) * (OL + 0.6) + len(b) * 7.4 + 8 for a, b in u_qat))
    b3 = 14.8
    hdr = g_h + b2 + b3
    qat = []
    for nom, hod, _k, jami in qatorlar:
        nq = _bol(nom, 9.6 * _KICH if jami else ON, (nom_w + (hod_w if (jami and tuman) else 0)) - (6 if jami else 12), jami)
        hq = _bol(", ".join(hod) if hod else ("" if jami else "-"), 6.8, hod_w - 8) if tuman else [""]
        qat.append((nq, hq, _JB if jami else max(_QB, max(len(nq) * (ON + 1.2), len(hq) * 8.0) + 4.5)))
    jami_h = qat[0][2]
    qat_h = sum(r[2] for r in qat[1:])
    pastki = PH - 22.0
    dy = 0.0
    if 165.7 + hdr + jami_h + qat_h > pastki:
        dy = -76.0
    top0 = 165.7 + dy
    sarlavha = _sarlavha(meta)

    def boshi():
        pdf.yangi_sahifa()
        fz = _sigdir(sarlavha, 12.4 * _KICH, ong - chap + 20, True, 8)
        pdf.matn(0, 119.5 + dy, sarlavha, fz, True, tekis="c", kenglik=PW)
        pdf.matn(0, 143.0 + dy, "D I N A M I K A" if meta.get("a") else "M A ' L U M O T", 12.4 * _KICH, True, rang=(1.0, 0.0, 0.0), tekis="c", kenglik=PW)
        pdf.matn(chap + 8, 156.3 + dy, "Hudud nomi:", 9.6 * _KICH)
        bx = chap + nom_w
        bw = max(100.0, _kenglik(_lotin(_hudud(meta)), 9.6 * _KICH, True) + 14)
        pdf.rect(bx, 145.3 + dy, bw, 14.8, chiziq=(0.0, 0.69, 0.941), qalinlik=0.9)
        pdf.matn(bx + 2.5, 156.3 + dy, _hudud(meta), 9.6 * _KICH, True, rang=(0.0, 0.4, 1.0))
        pdf.matn(ong - 330, 156.3 + dy, _davr(meta), 9.6 * _KICH, True, rang=(0.0, 0.0, 1.0), tekis="r", kenglik=330)
        y = top0
        # chap ustunlar sarlavhasi
        pdf.rect(chap, y, nom_w + hod_w, hdr, tola=_HDR, chiziq=QORA, qalinlik=0.5)
        fn = 11.0 * _KICH
        yc = y + hdr / 2
        if tuman:
            pdf.matn(chap, yc - 1.5, "Brigada", fn, True, tekis="c", kenglik=nom_w)
            pdf.matn(chap + nom_w, yc - 1.5, "Biriktirilgan", fn - 1, True, tekis="c", kenglik=hod_w)
            pdf.matn(chap + nom_w, yc + fn - 1, "hodimlar", fn - 1, True, tekis="c", kenglik=hod_w)
            pdf.chiziq(chap + nom_w, y, chap + nom_w, y + hdr, QORA, 0.5)
        else:
            pdf.matn(chap, yc - 1.5, "Hudud", fn, True, tekis="c", kenglik=nom_w)
            pdf.matn(chap, yc + fn - 0.5, "nomi", fn, True, tekis="c", kenglik=nom_w)
        for gnom, idx in guruhlar:
            gx = xs[idx[0]]
            gw = sum(cw[i][0] + cw[i][1] for i in idx)
            pdf.rect(gx, y, gw, g_h, tola=_HDR, chiziq=QORA, qalinlik=0.5)
            gf = _sigdir(gnom, 9.6 * _KICH, gw - 6, True, 6)
            pdf.matn(gx, y + g_h / 2 + gf * 0.34, gnom, gf, True, tekis="c", kenglik=gw)
        for i, u in enumerate(ust):
            ux, wv, wd = xs[i], cw[i][0], cw[i][1]
            w = wv + wd
            pdf.rect(ux, y + g_h, w, b2, tola=_HDR, chiziq=QORA, qalinlik=0.5)
            nq, hq = u_qat[i]
            tot = len(nq) * (OL + 0.6) + len(hq) * 7.4
            yy = y + g_h + (b2 - tot) / 2
            rang = _v_rang(u[0])
            for j, t in enumerate(nq):
                pdf.matn(ux, yy + j * (OL + 0.6) + OL * 0.85, t, OL - 0.4, True, rang=rang, tekis="c", kenglik=w)
            yy += len(nq) * (OL + 0.6)
            for j, t in enumerate(hq):
                pdf.matn(ux, yy + j * 7.4 + 6.0, t, 6.3, False, rang=_KULR, tekis="c", kenglik=w)
            y2 = y + g_h + b2
            pdf.rect(ux, y2, wv, b3, tola=_HDR, chiziq=QORA, qalinlik=0.5)
            pdf.rect(ux + wv, y2, wd, b3, tola=_HDR, chiziq=QORA, qalinlik=0.5)
            pdf.matn(ux, y2 + b3 / 2 + 2.2, "soni", 6.4, True, rang=_QIZ, tekis="c", kenglik=wv)
            pdf.strelka(ux + wv + wd / 2 - 3.4, y2 + b3 / 2, True, _UP, 5.0)
            pdf.strelka(ux + wv + wd / 2 + 3.4, y2 + b3 / 2, False, _DN, 5.0)
        return y + hdr

    y = boshi()
    for (nom, hod, katak, jami), (nq, hq, bal) in zip(qatorlar, qat):
        if y + bal > pastki + 0.6:
            y = boshi()
        yc = y + bal / 2
        if jami:
            bw = nom_w + hod_w
            pdf.rect(chap, y, bw, bal, tola=_JAMI, chiziq=QORA, qalinlik=0.5)
            fn = _sigdir(nom, 9.6 * _KICH, bw - 6, True, 6)
            pdf.matn(chap, yc + fn * 0.34, nom, fn, True, tekis="c", kenglik=bw)
        else:
            pdf.rect(chap, y, nom_w, bal, chiziq=QORA, qalinlik=0.5)
            lh = ON + 1.2
            yy = yc - len(nq) * lh / 2 + ON * 0.85
            for j, t in enumerate(nq):
                pdf.matn(chap + 8, yy + j * lh, t, ON)
            if tuman:
                pdf.rect(chap + nom_w, y, hod_w, bal, chiziq=QORA, qalinlik=0.5)
                yy = yc - len(hq) * 8.0 / 2 + 6.0
                for j, t in enumerate(hq):
                    pdf.matn(chap + nom_w + 4, yy + j * 8.0, t, 6.8, rang=(0.2, 0.2, 0.25))
        for i, c in enumerate(katak):
            x, wv, wd = xs[i], cw[i][0], cw[i][1]
            fon = _JAMI if jami else (_CREAM if i in muddat else None)
            pdf.rect(x, y, wv, bal, tola=fon, chiziq=QORA, qalinlik=0.5)
            pdf.rect(x + wv, y, wd, bal, tola=fon, chiziq=QORA, qalinlik=0.5)
            t = c["vt"] if c["v"] is not None else "-"
            fz = _sigdir(t, (9.6 * _KICH if jami else OL), wv - 5, True, 5)
            pdf.matn(x, yc + fz * 0.34, t, fz, True, rang=_v_rang(ust[i][0]), tekis="r", kenglik=wv - 4.2)
            yon, mt = _d(c["dt"])
            if yon:
                col = _d_rang(c["cls"])
                tw = _kenglik(_lotin(mt), DL, True)
                sx = x + wv + (wd - (6.6 + tw)) / 2
                pdf.strelka(sx + 2.8, yc, yon == "up", col, 6.0)
                pdf.matn(sx + 6.6, yc + DL * 0.34, mt, DL, True, rang=col)
        y += bal
