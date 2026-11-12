"""Sozlamalar (Telegram bot) va Telegram guruhlarga yuborish."""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import TelegramGuruh, TelegramIsh, TelegramSozlama
from .permissions import bor, ruxsat_kerak, tuman_ids
from .services import stats as S
from .services import tg_yuborish as TY
from .services import telegram as T

MANBALAR = {"dinamika": ("dinamika.telegram", ("xlsx", "pdf", "tumanlar")), "resp": ("resp_dinamika.telegram", ("xlsx", "pdf"))}
TUR_NOM = {"xlsx": "Excel", "pdf": "PDF", "tumanlar": "tumanlar kesimida PDF"}
ESKIRDI = datetime.timedelta(minutes=45)  # server qayta ishga tushsa, "jarayonda" qolib ketganlarni yopish uchun


def _niqob(token):
    return (token[:4] + "…" + token[-4:]) if len(token) > 12 else ("•" * len(token))


def _eskirganlarni_yop():
    TelegramIsh.objects.filter(holat="jarayonda", vaqt__lt=timezone.now() - ESKIRDI).update(
        holat="xato", xabar="Jarayon to'xtab qoldi (server qayta ishga tushgan bo'lishi mumkin).", tugadi=timezone.now())


# ---------------------------------------------------------------- sozlamalar sahifasi
@ruxsat_kerak("sozlamalar.korish")
def sozlamalar(request):
    sz = TelegramSozlama.olish()
    if request.method == "POST":
        if not bor(request.user, "sozlamalar.tahrirlash"):
            raise PermissionDenied
        amal = request.POST.get("amal")
        try:
            _amal(request, sz, amal)
        except T.TgXato as e:
            messages.error(request, f"Telegram: {e}")
        return redirect("sozlamalar")
    _eskirganlarni_yop()
    return render(request, "core/sozlamalar.html", {
        "token_bor": bool(sz.bot_token), "token_niqob": _niqob(sz.bot_token) if sz.bot_token else "", "bot_nomi": sz.bot_nomi,
        "guruhlar": TelegramGuruh.objects.all(), "ishlar": TelegramIsh.objects.select_related("yaratgan")[:15],
    })


def _amal(request, sz, amal):
    P = request.POST
    if amal == "token":
        token = (P.get("token") or "").strip()
        if not token:
            sz.bot_token, sz.bot_nomi = "", ""
            sz.save()
            messages.success(request, "Bot tokeni o'chirildi.")
            return
        info = T.bot_haqida(token)
        sz.bot_token, sz.bot_nomi = token, "@" + (info.get("username") or "")
        sz.save()
        messages.success(request, f"Bot ulandi: {sz.bot_nomi}. Endi uni guruhga admin qilib qo'shing va «Guruhlarni aniqlash» tugmasini bosing.")
    elif amal == "aniqlash":
        if not sz.bot_token:
            messages.error(request, "Avval bot tokenini kiriting.")
            return
        topilgan, chiqqan = T.guruhlarni_aniqla(sz.bot_token)
        yangi = 0
        for g in topilgan:
            obj, yaratildi = TelegramGuruh.objects.get_or_create(chat_id=g["chat_id"], defaults={"nom": g["nom"][:200], "tur": g["tur"] or ""})
            if not yaratildi:
                obj.nom, obj.tur = g["nom"][:200], g["tur"] or ""
                obj.save(update_fields=["nom", "tur"])
            yangi += int(yaratildi)
        if chiqqan:
            TelegramGuruh.objects.filter(chat_id__in=chiqqan).update(faol=False)
        if topilgan:
            messages.success(request, f"{len(topilgan)} ta guruh topildi, yangi qo'shilgani: {yangi}.")
        else:
            messages.warning(request, "Yangi guruh topilmadi. Botni guruhga admin qilib qo'shing, guruhga bitta xabar yozing va qayta urinib ko'ring. Yoki Chat ID ni qo'lda kiriting.")
    elif amal == "qosh":
        if not sz.bot_token:
            messages.error(request, "Avval bot tokenini kiriting.")
            return
        cid = (P.get("chat_id") or "").strip()
        if not cid:
            messages.error(request, "Chat ID kiriting.")
            return
        chat = T.chat_haqida(sz.bot_token, cid)
        nom = chat.get("title") or chat.get("username") or str(chat["id"])
        _o, yaratildi = TelegramGuruh.objects.update_or_create(chat_id=str(chat["id"]), defaults={"nom": nom[:200], "tur": chat.get("type") or "", "faol": True})
        holat_txt = "qo'shildi" if yaratildi else "yangilandi"
        messages.success(request, f"Guruh {holat_txt}: {nom}")
    elif amal in ("almashtir", "ochirish", "sinov"):
        g = get_object_or_404(TelegramGuruh, pk=P.get("id"))
        if amal == "almashtir":
            g.faol = not g.faol
            g.save(update_fields=["faol"])
            holat_txt = "yoqildi" if g.faol else "o'chirildi"
            messages.success(request, f"«{g.nom}»: yuborish {holat_txt}.")
        elif amal == "ochirish":
            g.delete()
            messages.success(request, f"«{g.nom}» ro'yxatdan olib tashlandi.")
        else:
            if not sz.bot_token:
                messages.error(request, "Avval bot tokenini kiriting.")
                return
            T.xabar_yubor(sz.bot_token, g.chat_id, "✅ Hodimlar nazorati: bot ulanishi sinovi muvaffaqiyatli.")
            messages.success(request, f"«{g.nom}» guruhiga sinov xabari yuborildi.")


# ---------------------------------------------------------------- yuborish
@login_required
def guruhlar(request):
    if not (bor(request.user, "dinamika.telegram") or bor(request.user, "resp_dinamika.telegram")):
        raise PermissionDenied
    sz = TelegramSozlama.olish()
    return JsonResponse({
        "token_bor": bool(sz.bot_token), "sozlamalar_bor": bor(request.user, "sozlamalar.korish"),
        "guruhlar": [{"id": g.id, "nom": g.nom, "tur": g.tur} for g in TelegramGuruh.objects.filter(faol=True)],
    })


def _tuman_tanla(user, x):
    ruxsat = tuman_ids(user)
    tid = int(x) if x and str(x).isdigit() else None
    if ruxsat is not None:
        if len(ruxsat) == 1:
            tid = ruxsat[0]
        elif tid not in ruxsat:
            tid = None
    return ruxsat, tid


def _sana(s):
    return S.aniq_sana(s) if s else None


@login_required
@require_POST
def yuborish(request):
    P = request.POST
    manba, tur = P.get("manba"), P.get("tur")
    if manba not in MANBALAR or tur not in MANBALAR[manba][1]:
        return JsonResponse({"xato": "Noto'g'ri so'rov."}, status=400)
    if not bor(request.user, MANBALAR[manba][0]):
        return JsonResponse({"xato": "Telegramga yuborish uchun ruxsatingiz yo'q."}, status=403)
    sz = TelegramSozlama.olish()
    if not sz.bot_token:
        return JsonResponse({"xato": "Bot tokeni kiritilmagan (Sozlamalar bo'limi)."}, status=400)
    idlar = [int(x) for x in P.getlist("guruh") if x.isdigit()]
    guruh_idlar = list(TelegramGuruh.objects.filter(pk__in=idlar, faol=True).values_list("id", flat=True))
    if not guruh_idlar:
        return JsonResponse({"xato": "Kamida bitta guruhni tanlang."}, status=400)
    b, a = _sana(P.get("b")), _sana(P.get("a"))
    if not b:
        return JsonResponse({"xato": "Sana noto'g'ri."}, status=400)

    if manba == "dinamika":
        if b not in S.mavjud_sanalar():
            return JsonResponse({"xato": "Bu sana uchun ma'lumot yuklanmagan."}, status=400)
        ruxsat, tid = _tuman_tanla(request.user, P.get("tuman"))
        sarlavha = f"Dinamika jadvali · {TUR_NOM[tur]} · {b:%d.%m.%Y}"
        def fayllar():
            return TY.dinamika_fayllari(tur, a, b, ruxsat, tid)
    else:
        sarlavha = f"Respublika dinamikasi · {TUR_NOM[tur]} · {b:%d.%m.%Y}"
        def fayllar():
            return TY.resp_fayllari(tur, a, b)

    ish = TelegramIsh.objects.create(sarlavha=sarlavha[:200], yaratgan=request.user)
    TY.fonda_boshlash(ish.id, guruh_idlar, fayllar)
    return JsonResponse({"id": ish.id, "guruhlar": len(guruh_idlar)})


@login_required
def holat(request, pk):
    ish = get_object_or_404(TelegramIsh, pk=pk)
    if ish.yaratgan_id != request.user.id and not bor(request.user, "sozlamalar.korish"):
        raise PermissionDenied
    _eskirganlarni_yop()
    ish.refresh_from_db()
    return JsonResponse({"id": ish.id, "holat": ish.holat, "holat_txt": ish.get_holat_display(), "jami": ish.jami, "yuborildi": ish.yuborildi,
                         "xato_soni": ish.xato_soni, "xabar": ish.xabar[:600], "sarlavha": ish.sarlavha})
