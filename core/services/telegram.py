"""Telegram Bot API bilan ishlash (qo'shimcha kutubxonasiz, faqat standart urllib)."""
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
import uuid

API = "https://api.telegram.org"


class TgXato(Exception):
    def __init__(self, xabar, kod=None, parametrlar=None):
        super().__init__(xabar)
        self.kod = kod
        self.parametrlar = parametrlar or {}


def _chaqir(token, metod, maydonlar=None, fayl=None, timeout=60):
    """fayl = (maydon_nomi, fayl_nomi, bytes). Javobning 'result' qismini qaytaradi."""
    url = f"{API}/bot{token}/{metod}"
    if fayl:
        chegara = uuid.uuid4().hex
        qismlar = []
        for k, v in (maydonlar or {}).items():
            qismlar.append(f'--{chegara}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
        maydon, nom, data = fayl
        tur = mimetypes.guess_type(nom)[0] or "application/octet-stream"
        nom_q = nom.replace('"', "'")
        qismlar.append(f'--{chegara}\r\nContent-Disposition: form-data; name="{maydon}"; filename="{nom_q}"\r\nContent-Type: {tur}\r\n\r\n'.encode("utf-8"))
        qismlar.append(data)
        qismlar.append(f"\r\n--{chegara}--\r\n".encode("utf-8"))
        body = b"".join(qismlar)
        sarlavha = {"Content-Type": f"multipart/form-data; boundary={chegara}"}
    else:
        body = json.dumps(maydonlar or {}).encode("utf-8")
        sarlavha = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=sarlavha, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            javob = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            javob = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa
            raise TgXato(f"Telegram javobi: HTTP {e.code}", e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TgXato(f"Telegramga ulanib bo'lmadi: {getattr(e, 'reason', e)}")
    if not javob.get("ok"):
        raise TgXato(javob.get("description") or "Noma'lum xato", javob.get("error_code"), javob.get("parameters"))
    return javob.get("result")


def bot_haqida(token):
    """getMe: bot ma'lumoti ({'username': ..., 'first_name': ...})."""
    return _chaqir(token, "getMe", timeout=20)


def azo_holati(token, chat_id, user_id):
    """getChatMember: botning guruhdagi holati (creator | administrator | member | restricted | left | kicked)."""
    return _chaqir(token, "getChatMember", {"chat_id": chat_id, "user_id": user_id}, timeout=20)


def chat_haqida(token, chat_id):
    return _chaqir(token, "getChat", {"chat_id": chat_id}, timeout=20)


_NOLLAR = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00a0"), None)


def chat_nomzodlari(matn):
    """Foydalanuvchi kiritgan matndan (Chat ID, @username, t.me havolasi) Telegram uchun mumkin bo'lgan chat_id lar ro'yxati."""
    m = (matn or "").translate(_NOLLAR).strip().strip("\"'`<>[]() ").replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    if not m:
        return []
    h = re.match(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(.+)$", m, re.I)
    if h:
        yol = h.group(1).split("?")[0].strip("/")
        if yol.startswith("+") or yol.lower().startswith("joinchat"):
            raise TgXato("Bu taklif havolasi. Taklif havolasidan Chat ID olib bo'lmaydi: guruhning Chat ID sini (masalan -1001234567890) yoki ochiq guruh bo'lsa @username ni kiriting.")
        c = re.match(r"^c/(\d+)", yol)
        if c:
            return ["-100" + c.group(1)]
        m = "@" + yol.split("/")[0]
    if m.startswith("@"):
        return [m]
    raqam = re.sub(r"\s+", "", m)
    if re.fullmatch(r"-?\d+", raqam):
        if raqam.startswith("-100"):
            return [raqam]
        if raqam.startswith("-"):
            d = raqam[1:]
            return [raqam, "-100" + d] if len(d) >= 10 else [raqam]
        return ["-100" + raqam, "-" + raqam]
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,}", m):
        return ["@" + m]
    raise TgXato("Chat ID noto'g'ri ko'rinishda. Masalan: -1001234567890 (yoki ochiq guruh uchun @guruh_nomi).")


def chat_topish(token, matn):
    """Kiritilgan matn bo'yicha guruhni topadi (turli ko'rinishlarni sinab ko'radi,
    oddiy guruh supergruppaga aylangan bo'lsa yangi ID ga o'tadi). getChat natijasini qaytaradi."""
    oxirgi = None
    for cid in chat_nomzodlari(matn):
        for _ in range(2):
            try:
                return chat_haqida(token, cid)
            except TgXato as e:
                oxirgi = e
                yangi = (e.parametrlar or {}).get("migrate_to_chat_id")
                if yangi:
                    cid = str(yangi)
                    continue
                if e.kod is None:  # tarmoq xatosi: boshqa ko'rinishni sinashning foydasi yo'q
                    raise
                break
    raise oxirgi or TgXato("Guruh topilmadi")


def xato_matni(e):
    """Telegram xatosini tushunarli o'zbekcha matnga aylantiradi."""
    t = str(e)
    k = t.lower()
    if "chat not found" in k:
        return ("Guruh topilmadi: bot bu guruhga qo'shilmagan yoki Chat ID noto'g'ri. Botni guruhga qo'shib administrator qiling, "
                "so'ng guruhga bitta xabar yozing va «Guruhlarni aniqlash» ni bosing yoki to'g'ri Chat ID ni kiriting "
                "(supergruppa ID si -100 bilan boshlanadi).")
    if "bot was kicked" in k or "bot is not a member" in k or "not enough rights" in k or "have no rights" in k:
        return f"Bot bu guruhda yo'q yoki huquqi yetarli emas (guruhga administrator qilib qo'shing). Telegram: {t}"
    if "unauthorized" in k or e.kod == 401:
        return "Bot tokeni noto'g'ri yoki bekor qilingan. Sozlamalarda tokenni yangilang."
    if "terminated by other getupdates" in k or "webhook is active" in k or e.kod == 409:
        return ("Bu bot boshqa joyda ishlatilmoqda (webhook yoki boshqa getUpdates). Guruhni aniqlab bo'lmaydi: "
                "Chat ID ni qo'lda kiriting.")
    return t


def xabar_yubor(token, chat_id, matn):
    return _chaqir(token, "sendMessage", {"chat_id": chat_id, "text": matn[:4000]}, timeout=30)


def _fayl_yubor(metod, maydon, token, chat_id, fayl_nomi, data, izoh="", urinish=4):
    """Faylni yuboradi. 429 (tez-tez yuborish) bo'lsa kutib qayta urinadi.
    Qaytaradi: (natija, chat_id) - guruh supergruppaga aylangan bo'lsa chat_id yangilanadi."""
    for n in range(urinish):
        try:
            res = _chaqir(token, metod, ({"chat_id": chat_id, "caption": izoh[:1000]} if izoh else {"chat_id": chat_id}), (maydon, fayl_nomi, data), timeout=180)
            return res, chat_id
        except TgXato as e:
            if e.kod == 429 and n < urinish - 1:
                time.sleep(min(int(e.parametrlar.get("retry_after", 5)) + 1, 60))
                continue
            yangi = e.parametrlar.get("migrate_to_chat_id")
            if yangi and n < urinish - 1:
                chat_id = str(yangi)
                continue
            if n < urinish - 1 and e.kod is None:  # tarmoq xatosi: qisqa kutib qayta urinish
                time.sleep(3)
                continue
            e.yangi_chat_id = chat_id
            raise
    raise TgXato("Yuborib bo'lmadi")


def hujjat_yubor(token, chat_id, fayl_nomi, data, izoh="", urinish=4):
    """Faylni hujjat sifatida yuboradi. Qaytaradi: (natija, chat_id)."""
    return _fayl_yubor("sendDocument", "document", token, chat_id, fayl_nomi, data, izoh, urinish)


def rasm_yubor(token, chat_id, fayl_nomi, data, izoh="", urinish=4):
    """PNG rasmni (Telegramda darhol ko'rinadigan) fotosurat sifatida yuboradi."""
    return _fayl_yubor("sendPhoto", "photo", token, chat_id, fayl_nomi, data, izoh, urinish)


def guruhlarni_aniqla(token):
    """Bot a'zo bo'lgan guruh/kanallarni getUpdates orqali topadi.
    Qaytaradi: (topilganlar [{chat_id, nom, tur}], chiqarilganlar [chat_id])."""
    yangilar = _chaqir(token, "getUpdates", {"limit": 100, "timeout": 0, "allowed_updates": ["my_chat_member", "message", "channel_post", "edited_message"]}, timeout=30)
    topilgan, chiqqan, oxirgi = {}, set(), None
    for u in yangilar or []:
        oxirgi = u.get("update_id", oxirgi)
        chat, holat = None, None
        if "my_chat_member" in u:
            m = u["my_chat_member"]
            chat, holat = m.get("chat"), (m.get("new_chat_member") or {}).get("status")
        else:
            for k in ("message", "channel_post", "edited_message"):
                if k in u:
                    chat = u[k].get("chat")
                    break
        if not chat or chat.get("type") not in ("group", "supergroup", "channel"):
            continue
        cid = str(chat["id"])
        if holat in ("left", "kicked"):
            chiqqan.add(cid)
            topilgan.pop(cid, None)
            continue
        chiqqan.discard(cid)
        topilgan[cid] = {"chat_id": cid, "nom": chat.get("title") or cid, "tur": chat.get("type")}
    if oxirgi is not None:  # ko'rilgan yangilanishlarni tasdiqlaymiz (keyingi safar takrorlanmasin)
        try:
            _chaqir(token, "getUpdates", {"offset": oxirgi + 1, "limit": 1, "timeout": 0}, timeout=20)
        except TgXato:
            pass
    return list(topilgan.values()), sorted(chiqqan)
