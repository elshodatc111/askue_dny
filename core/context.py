from .permissions import is_admin, rol_nomi, ruxsatlar, tuman_ids


def umumiy(request):
    u = request.user
    if not u.is_authenticated:
        return {}
    ids = tuman_ids(u)
    r = ruxsatlar(u)
    rx = {k.replace(".", "_"): True for k in r}
    return {
        "admin_mi": is_admin(u),
        "rol_nomi": rol_nomi(u),
        "butun_viloyat": ids is None,
        "rx": rx,
        "boshqaruv_bor": any(k in r for k in ("yuklash.korish", "resp_yuklash.korish", "brigadalar.korish", "tp_kochirish.korish", "foydalanuvchilar.korish")),
    }
