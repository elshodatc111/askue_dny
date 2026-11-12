"""Telegram Bot API bilan ishlash (qo'shimcha kutubxonasiz, faqat standart urllib)."""
import json
import mimetypes
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


def chat_haqida(token, chat_id):
    return _chaqir(token, "getChat", {"chat_id": chat_id}, timeout=20)


def xabar_yubor(token, chat_id, matn):
    return _chaqir(token, "sendMessage", {"chat_id": chat_id, "text": matn[:4000]}, timeout=30)


def hujjat_yubor(token, chat_id, fayl_nomi, data, izoh="", urinish=4):
    """Faylni hujjat sifatida yuboradi. 429 (tez-tez yuborish) bo'lsa kutib qayta urinadi.
    Qaytaradi: (natija, chat_id) - guruh supergruppaga aylangan bo'lsa chat_id yangilanadi."""
    for n in range(urinish):
        try:
            res = _chaqir(token, "sendDocument", {"chat_id": chat_id, "caption": izoh[:1000]}, ("document", fayl_nomi, data), timeout=180)
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
