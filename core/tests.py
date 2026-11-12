import datetime

import openpyxl
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import TP, Brigada, Tuman, Yuklama
from .services import importer
from .services import stats as S
from .services.names import hodimlarni_ajrat, norm, tp_kalit, tr_norm


class NomlarTest(TestCase):
    def test_hodimlar_ajratish(self):
        self.assertEqual(hodimlarni_ajrat("Haitov.SH Ashurova.M Qurbonova.D"), ["Haitov.SH", "Ashurova.M", "Qurbonova.D"])
        self.assertEqual(hodimlarni_ajrat("TEMIROV ABBOS,AMINOVA MOHINUR"), ["TEMIROV ABBOS", "AMINOVA MOHINUR"])
        self.assertEqual(hodimlarni_ajrat("MEYLIYEV FERUZ. ESHMIRZAYEVA GAVHAR. NIYOZOV TOLIB."), ["MEYLIYEV FERUZ", "ESHMIRZAYEVA GAVHAR", "NIYOZOV TOLIB"])
        self.assertEqual(hodimlarni_ajrat("Daminov Asqar Xolboyev Bekzod Ibodova Nargiza"), ["Daminov Asqar", "Xolboyev Bekzod", "Ibodova Nargiza"])
        self.assertEqual(hodimlarni_ajrat("KAMOLOV QUVONCHBEK ABDISAID UG'LI . BOYQOBILOV NORMUROD"), ["KAMOLOV QUVONCHBEK ABDISAID UG'LI", "BOYQOBILOV NORMUROD"])
        self.assertEqual(hodimlarni_ajrat("JABBOROV XUSAN"), ["JABBOROV XUSAN"])
        self.assertEqual(hodimlarni_ajrat(""), [])

    def test_tp_kalit(self):
        self.assertEqual(tr_norm("00284"), "284")
        self.assertEqual(tp_kalit("Koson TETK", "NS A", "F 10 kV", "00284"), tp_kalit("Koson TETK", "ns a", "F 10 kV", "284"))
        self.assertEqual(norm("G‘uzor"), norm("G'uzor"))

    def test_bucket(self):
        self.assertEqual([importer.bucket(x) for x in (0, 1, 2, 7, 8, 30, 31, 90, 91, None)], ["b0", "b0", "b1", "b1", "b2", "b2", "b3", "b3", "b4", "b0"])

    def test_tasniflash(self):
        self.assertEqual(importer.holat_tasnif("Offline"), "offline")
        self.assertEqual(importer.holat_tasnif("Online"), "online")
        self.assertEqual(importer.holat_tasnif("Оффлайн"), "offline")
        self.assertEqual(importer.holat_tasnif("Unknown"), "noma'lum")
        self.assertEqual(importer.turi_tasnif("Residential"), "aholi")
        self.assertEqual(importer.turi_tasnif("Industrial"), "ulgurji")
        self.assertEqual(importer.turi_tasnif("Balance Meter"), "balans")
        self.assertEqual(importer.turi_tasnif("Аҳоли"), "aholi")


def _xlsx(path, sarlavha, qatorlar, sarlavha_oldidan=()):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in sarlavha_oldidan:
        ws.append(r)
    ws.append(sarlavha)
    for q in qatorlar:
        ws.append(q)
    wb.save(path)


@override_settings(UPLOAD_DIR="/tmp")
class ImportTest(TestCase):
    def setUp(self):
        import tempfile

        self.d = tempfile.mkdtemp()

    def _bajar(self, nom, sana, **kw):
        info = importer.aniqlash(f"{self.d}/{nom}", nom)
        y = Yuklama.objects.create(tur=info["tur"], sana=sana)
        importer.sinxron([{"yuklama_id": y.id, "path": f"{self.d}/{nom}", "header": info["header"], "tur": info["tur"]}])
        return Yuklama.objects.get(pk=y.pk), info

    def test_butun_oqim(self):
        # Hududiy tuzilma: ustun nomlari ixtiyoriy tilda bo'lishi mumkin
        area_h = ["№", "X", "Y", "Z", "ESP", "a", "Podst", "b", "Feeder", "c", "TP", "Egasi", "Mas'ul", "Hudud", "ID", "Tel"]
        _xlsx(f"{self.d}/area.xlsx", area_h, [
            [1, "10000", "Q", "10245", "Koson TETK", "1", "NS A 35/10 kV", "1", "F1 10 kV", "00284", "284", "ESP", "Ali Vali, Guli Gul", "Koson", "30801772560032, 30801772560033", "+998901234567"],
            [2, "10000", "Q", "10245", "Koson TETK", "1", "NS A 35/10 kV", "1", "F1 10 kV", "00285", "285", "ESP", "Ali Vali, Guli Gul", "Koson", "30801772560032, 30801772560033", "+998901234567"],
            [3, "10000", "Q", "10245", "Qarshi ShETK", "1", "NS B 35/10 kV", "1", "F2 6 kV", "00001", "7", "ESP", "", "Q", "", ""],
        ], sarlavha_oldidan=[["Hisobot"], [None, "Area:", "Q", None, None, "Total:", 3, None, None, "Vaqt:", datetime.datetime(2026, 11, 12, 11, 50)]])
        y, info = self._bajar("area.xlsx", datetime.date(2026, 11, 12))
        self.assertEqual(info["tur"], "area")
        self.assertEqual(info["sana"], datetime.date(2026, 11, 12))
        self.assertEqual(y.holat, "tayyor", y.xabar)
        self.assertEqual(TP.objects.count(), 3)
        b = Brigada.objects.get(tuman__nom="Koson TETK")
        self.assertEqual([h.ism for h in b.hodimlar.all()], ["Ali Vali", "Guli Gul"])
        self.assertEqual(b.tplar.count(), 2)
        self.assertEqual(TP.objects.filter(brigada__isnull=True).count(), 1)

        # Aloqasiz hisoblagichlar (16 ustun, 13-ustun vaqt)
        nm_h = ["No", "ESP", "Sub", "Feeder", "TR", "Acc", "Type", "Name", "Meter", "Comm", "Mgr", "Phone", "Days", "Time", "GPS", "Addr"]
        _xlsx(f"{self.d}/nm.xlsx", nm_h, [
            [1, "Koson TETK", "NS A 35/10 kV", "F1 10 kV", "284", "1", "Residential", "X", "111", "PLC", "Ali Vali, Guli Gul", None, 3, "10:00:00", "39.1,66.2", "adr"],
            [2, "Koson TETK", "NS A 35/10 kV", "F1 10 kV", "00285", "2", "Industrial", "Y", "112", "GPRS", "Ali Vali, Guli Gul", None, 100, "10:00:00", ",", "adr"],
        ])
        y, info = self._bajar("nm.xlsx", datetime.date(2026, 11, 12))
        self.assertEqual(info["tur"], "nometer")
        d = S.dinamika("nometer", None, datetime.date(2026, 11, 12), None)
        jami = {c["key"]: c["v"] for c in d["jami"]["katak"]}
        self.assertEqual((jami["jami"], jami["aholi"], jami["ulgurji"], jami["b1"], jami["b4"]), (2, 1, 1, 1, 1))

        # Konsentratorlar (19 ustun)
        on_h = ["a"] * 19
        on_h = [f"c{i}" for i in range(19)]
        _xlsx(f"{self.d}/dcu.xlsx", on_h, [
            ["Koson TETK", "NS A 35/10 kV", "F1 10 kV", "284", "DCU", "129205000001", "Online", "12/11/2026 11:00:00", "Ucell", 39.1, 66.2, "1.2.3.4", 1, "s", None, None, None, None, None],
            ["Koson TETK", "NS A 35/10 kV", "F1 10 kV", "285", "DCU", "129205000002", "Offline", "01/11/2026 11:00:00", "Ucell", 39.1, 66.2, "1.2.3.5", 1, "s", None, None, None, None, None],
        ])
        y, info = self._bajar("dcu.xlsx", datetime.date(2026, 11, 12))
        self.assertEqual(info["tur"], "dcu")
        d = S.dinamika("dcu", None, datetime.date(2026, 11, 12), None)
        jami = {c["key"]: c["v"] for c in d["jami"]["katak"]}
        self.assertEqual((jami["jami"], jami["online"], jami["offline"], jami["k3"]), (2, 1, 1, 1))  # 11 kun
        self.assertEqual(jami["k30"], 0)  # 3 kundan ortiq: 1 ta, 30 kundan ortiq: yo'q

        # Brigadalar kesimi
        tuman = Tuman.objects.get(nom="Koson TETK")
        d = S.dinamika("dcu", None, datetime.date(2026, 11, 12), None, tuman.id)
        self.assertEqual(d["qatorlar"][0]["nom"], "Brigada 1")
        self.assertEqual(d["qatorlar"][0]["hodimlar"], ["Ali Vali", "Guli Gul"])

        # Eksport: Excel va PDF
        from .services import eksport

        d = S.dinamika("dcu", None, datetime.date(2026, 11, 12), None, tuman.id)
        meta = {"tur_nom": "Konsentratorlar", "a": None, "b": datetime.date(2026, 11, 12), "tuman": "Koson", "tur": "dcu"}
        r = eksport.dinamika_pdf(d, meta)
        self.assertTrue(r.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", r.content[-20:])
        r = eksport.dinamika_xlsx(d, meta)
        wb = openpyxl.load_workbook(__import__("io").BytesIO(r.content))
        self.assertEqual(wb.active["A8"].value, "Brigada")

        # 4 dinamika bitta PDF va ZIP (tumanlar -> brigadalar)
        from django.http import HttpRequest
        import zipfile, io
        from django.test import Client
        c = Client(); c.login(username="admin_t", password="x") if False else None
        data = eksport.kopchilik_pdf([(S.dinamika(t, None, datetime.date(2026, 11, 12), None, tuman.id), {"tur_nom": "x", "a": None, "b": datetime.date(2026, 11, 12), "tuman": "Koson", "tur": t}) for t in S.TURLAR])
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        self.assertGreaterEqual(data.count(b"/Type /Page "), 4)

        # Qayta yuklash eskisini almashtiradi
        self._bajar("dcu.xlsx", datetime.date(2026, 11, 12))
        self.assertEqual(Yuklama.objects.filter(tur="dcu").count(), 1)

    def test_notogri_fayl(self):
        _xlsx(f"{self.d}/x.xlsx", ["a", "b"], [[1, 2]])
        with self.assertRaises(importer.ImportXato):
            importer.aniqlash(f"{self.d}/x.xlsx", "x.xlsx")


class RuxsatTest(TestCase):
    def test_kirish_talab_qilinadi(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)

    def test_oddiy_hodim_yuklay_olmaydi(self):
        t = Tuman.objects.create(nom="Koson TETK")
        u = User.objects.create_user("h", "", "x12345")
        u.profil.rol = "tuman_hodim"
        u.profil.tuman = t
        u.profil.save()
        self.client.login(username="h", password="x12345")
        self.assertEqual(self.client.get("/yuklash/").status_code, 403)
        self.assertEqual(self.client.get("/").status_code, 200)


class RuxsatMatritsaTest(TestCase):
    def setUp(self):
        self.t = Tuman.objects.create(nom="Koson TETK")
        self.u = User.objects.create_user("h", "", "x12345")
        self.u.profil.rol = "tuman_hodim"
        self.u.profil.tuman = self.t
        self.u.profil.save()
        Yuklama.objects.create(tur="dcu", sana=datetime.date(2026, 11, 12), holat="tayyor")

    def _kirish(self):
        self.client.login(username="h", password="x12345")

    def test_standart_ruxsatlar(self):
        from .permissions import bor

        u = User.objects.get(pk=self.u.pk)
        self.assertTrue(bor(u, "dinamika.eksport"))
        self.assertFalse(bor(u, "yuklash.yuklash"))
        self.assertFalse(bor(u, "foydalanuvchilar.korish"))

    def test_eksport_olib_qoyiladi(self):
        self.u.profil.ruxsatlar = {"dinamika.eksport": False}
        self.u.profil.save()
        self._kirish()
        self.assertEqual(self.client.get("/dinamika/").status_code, 200)
        self.assertEqual(self.client.get("/dinamika/?format=xlsx").status_code, 403)
        self.assertEqual(self.client.get("/dinamika/?format=pdf").status_code, 403)

    def test_eksport_ruxsati_bilan(self):
        self._kirish()
        r = self.client.get("/dinamika/?tur=dcu&format=pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        r = self.client.get("/dinamika/?tur=dcu&format=xlsx")
        self.assertEqual(r.status_code, 200)

    def test_bolim_yopiladi(self):
        self.u.profil.ruxsatlar = {"xarita.korish": False, "bosh.korish": False}
        self.u.profil.save()
        self._kirish()
        self.assertEqual(self.client.get("/xarita/").status_code, 403)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)  # ruxsat berilgan boshqa sahifaga o'tkaziladi

    def test_yuklash_ruxsat_berilsa(self):
        self.u.profil.ruxsatlar = {"yuklash.korish": True, "yuklash.yuklash": True}
        self.u.profil.save()
        self._kirish()
        self.assertEqual(self.client.get("/yuklash/").status_code, 200)

    def test_foydalanuvchilar_faqat_admin(self):
        self.u.profil.ruxsatlar = {"foydalanuvchilar.korish": True}
        self.u.profil.save()
        self._kirish()
        self.assertEqual(self.client.get("/foydalanuvchilar/").status_code, 403)

    def test_admin_ruxsat_saqlaydi(self):
        a = User.objects.create_superuser("adm", "", "adm12345")
        self.client.login(username="adm", password="adm12345")
        r = self.client.post(f"/foydalanuvchilar/{self.u.pk}/", {
            "username": "h", "ism": "H", "rol": "tuman_hodim", "tuman": str(self.t.id), "faol": "1",
            "rx": ["bosh.korish", "dinamika.korish", "royxat.korish", "xarita.korish", "brigadalar.korish", "brigadalar.tahrirlash"],
        })
        self.assertEqual(r.status_code, 302)
        pr = User.objects.get(pk=self.u.pk).profil
        self.assertEqual(pr.ruxsatlar, {"dinamika.eksport": False, "royxat.eksport": False, "brigadalar.korish": True, "brigadalar.tahrirlash": True})
        self.assertEqual(self.client.get(f"/foydalanuvchilar/{self.u.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/foydalanuvchilar/").status_code, 200)
        self.assertEqual(self.client.get("/foydalanuvchilar/yangi/").status_code, 200)


# ---------------------------------------------------------------- respublika dinamikasi
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.urls import reverse  # noqa: E402

from .models import RespKun, RespYuklama  # noqa: E402
from .permissions import BARCHA  # noqa: E402
from .services import resp as R  # noqa: E402
from .services import resp_eksport as RE  # noqa: E402

_TD = os.path.join(os.path.dirname(__file__), "testdata")
PDF9 = os.path.join(_TD, "resp_09.11.2026.pdf")   # dushanba
PDF12 = os.path.join(_TD, "resp_12.11.2026.pdf")  # payshanba


class RespParserTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = R.oqi(PDF9, "09.11.2026.pdf")
        cls.b = R.oqi(PDF12, "12.11.2026.pdf")

    def test_sana_va_tekshiruv(self):
        self.assertEqual(self.b["sana"], datetime.date(2026, 11, 12))
        self.assertEqual(self.a["sana"], datetime.date(2026, 11, 9))
        for r in (self.a, self.b):
            self.assertIsNone(r["xato"])
            self.assertEqual(r["ogohlantirish"], [])  # tuman yig'indilari "Jami" ga mos
            self.assertEqual(sorted(r["malumot"]), sorted(R.SAHIFALAR))
            for rows in r["malumot"].values():
                self.assertEqual(len(rows), 18)  # 17 tuman + Jami

    def test_qiymatlar(self):
        m = self.b["malumot"]
        jami = lambda k: next(x for x in m[k] if x["jami"])["v"]  # noqa: E731
        self.assertEqual(jami("r1")["tr"], 17530)
        self.assertEqual(jami("r2")["jami"], 24958)
        self.assertEqual(jami("r2")["foiz"], 3.1)
        self.assertEqual(jami("r3")["direct"], 367)
        self.assertEqual(jami("r4")["muam"], 347)
        self.assertEqual(jami("r6")["a_ob"], 718503)
        self.assertEqual(jami("r7")["manfiy"], 2784)
        self.assertEqual(jami("r8")["casbor"], 1046)
        kasbi = next(x for x in m["r2"] if x["nom"] == "Kasbi t.")["v"]
        self.assertEqual(kasbi["jami"], 1078)

    def test_dinamika_tanlangan_sanaga_nisbatan(self):
        j = R.jadval("r2", self.b["malumot"], self.a["malumot"])
        jami = next(q for q in j["qatorlar"] if q["jami"])
        self.assertEqual(len(jami["katak"]), len(j["ustunlar"]))
        d = [(u["key"], k["d"]) for u, k in zip(j["ustunlar"], jami["katak"]) if u["kind"] == "d"]
        kutilgan = self.b["malumot"]["r2"][0]["v"]["jami"] - self.a["malumot"]["r2"][0]["v"]["jami"]
        self.assertEqual(dict(d)["jami_d"], kutilgan)
        # solishtirishsiz o'zgarish yo'q
        j0 = R.jadval("r2", self.b["malumot"], None)
        self.assertTrue(all(k["t"] == "" for u, k in zip(j0["ustunlar"], j0["qatorlar"][0]["katak"]) if u["kind"] == "d"))

    def test_notogri_pdf(self):
        r = R.oqi(io.BytesIO(b"bu pdf emas"), "x.pdf")
        self.assertTrue(r["xato"])

    def test_eksport(self):
        js = R.barcha_jadvallar(self.b["malumot"], self.a["malumot"])
        meta = {"sana": datetime.date(2026, 11, 12), "baza": datetime.date(2026, 11, 9), "yuklangan": None}
        self.assertTrue(RE.pdf(js, meta).startswith(b"%PDF"))
        wb = openpyxl.load_workbook(io.BytesIO(RE.xlsx(js, meta)))
        self.assertEqual(len(wb.sheetnames), 7)


class RespViewTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ov = override_settings(UPLOAD_DIR=self.tmp)
        self.ov.enable()
        self.admin = User.objects.create_superuser("admin", password="Admin@12345")
        self.c = self.client
        self.c.login(username="admin", password="Admin@12345")

    def tearDown(self):
        self.ov.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _yukla(self, yol, nom, **extra):
        with open(yol, "rb") as f:
            return self.c.post(reverse("resp_yuklash"), {"fayllar": SimpleUploadedFile(nom, f.read(), content_type="application/pdf"), **extra})

    def test_yuklash_almashtirish_va_yuklab_olish(self):
        r = self._yukla(PDF12, "a.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(RespYuklama.objects.filter(faol=True).count(), 1)
        self._yukla(PDF12, "b.pdf")
        self.assertEqual(RespYuklama.objects.count(), 2)
        self.assertEqual(RespYuklama.objects.filter(faol=True).count(), 1)
        y = RespYuklama.objects.get(faol=True)
        self.assertEqual(y.fayl_nomi, "b.pdf")
        r = self.c.get(reverse("resp_fayl_yuklab", args=[y.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content)[:4], b"%PDF")
        # faol o'chirilsa, avvalgisi amalda bo'ladi
        self.c.post(reverse("resp_fayl_ochirish", args=[y.id]))
        self.assertEqual(RespYuklama.objects.filter(faol=True).count(), 1)
        self.assertEqual(RespYuklama.objects.get(faol=True).fayl_nomi, "a.pdf")

    def test_dam_olish_kunlari_va_qolda_belgilash(self):
        # 09.11.2026 dushanba (ko'rinadi), 12.11 payshanba
        self._yukla(PDF9, "9.pdf")
        self._yukla(PDF12, "12.pdf")
        r = self.c.get(reverse("resp_dinamika"))
        self.assertContains(r, "Respublika dinamikasi")
        self.assertEqual(r.context["b"], datetime.date(2026, 11, 12))
        self.assertEqual(r.context["a"], datetime.date(2026, 11, 9))  # oy boshiga nisbatan
        # 09.11 ni dam olish kuni qilamiz -> ko'rinmaydi
        self.c.post(reverse("resp_kun"), {"sana": "2026-11-09", "holat": "dam"})
        r = self.c.get(reverse("resp_dinamika"))
        self.assertIsNone(r.context["a"])
        self.assertEqual([k["iso"] for k in r.context["kunlar_b"]], ["2026-11-12"])
        self.c.post(reverse("resp_kun"), {"sana": "2026-11-09", "holat": "standart"})
        self.assertEqual(RespKun.objects.count(), 0)
        # shanba kuniga yuklangan PDF (sanani qo'lda: 14.11 shanba) standart bo'yicha yashirin, "ish" deb belgilansa ko'rinadi
        self._yukla(PDF12, "s.pdf", sana="2026-11-14")
        r = self.c.get(reverse("resp_dinamika"))
        self.assertNotIn("2026-11-14", [k["iso"] for k in r.context["kunlar_b"]])
        self.c.post(reverse("resp_kun"), {"sana": "2026-11-14", "holat": "ish"})
        r = self.c.get(reverse("resp_dinamika"))
        self.assertIn("2026-11-14", [k["iso"] for k in r.context["kunlar_b"]])

    def test_eksport_va_sahifalar(self):
        self._yukla(PDF9, "9.pdf")
        self._yukla(PDF12, "12.pdf")
        for s in R.SAHIFALAR:
            self.assertEqual(self.c.get(reverse("resp_dinamika"), {"s": s, "a": "old"}).status_code, 200)
        r = self.c.get(reverse("resp_dinamika"), {"format": "pdf", "a": "oy"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        r = self.c.get(reverse("resp_dinamika"), {"format": "xlsx"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content[:2], b"PK")

    def test_ruxsatlar(self):
        u = User.objects.create_user("hodim", password="Hodim@12345")
        c = self.client_class()
        c.login(username="hodim", password="Hodim@12345")
        for url in ("resp_dinamika", "resp_yuklash"):
            self.assertEqual(c.get(reverse(url)).status_code, 403)
        # admin ruxsat beradi
        pr = u.profil
        pr.ruxsatlar = {"resp_dinamika.korish": True}
        pr.save()
        self.assertEqual(c.get(reverse("resp_dinamika")).status_code, 200)
        self.assertEqual(c.get(reverse("resp_yuklash")).status_code, 403)
        self.assertEqual(c.post(reverse("resp_kun"), {"sana": "2026-11-09", "holat": "ish"}).status_code, 403)
        self.assertEqual(c.get(reverse("resp_dinamika"), {"format": "pdf"}).status_code, 403)
        self.assertTrue(all(k in BARCHA for k in ("resp_dinamika.kunlar", "resp_yuklash.yuklash", "resp_fayllar.yuklab", "resp_fayllar.ochirish")))
