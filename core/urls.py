from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views, views_resp, views_tg

urlpatterns = [
    path("kirish/", auth_views.LoginView.as_view(template_name="core/kirish.html", redirect_authenticated_user=True), name="kirish"),
    path("chiqish/", auth_views.LogoutView.as_view(), name="chiqish"),
    path("parol/", auth_views.PasswordChangeView.as_view(template_name="core/parol.html", success_url=reverse_lazy("bosh")), name="parol"),
    path("", views.bosh, name="bosh"),
    path("dinamika/", views.dinamika, name="dinamika"),
    path("respublika/", views_resp.resp_dinamika, name="resp_dinamika"),
    path("respublika/kun/", views_resp.resp_kun, name="resp_kun"),
    path("respublika/yuklash/", views_resp.resp_yuklash, name="resp_yuklash"),
    path("respublika/yuklash/holat/", views_resp.resp_yuklash_holat, name="resp_yuklash_holat"),
    path("respublika/fayllar/<int:pk>/yuklab/", views_resp.resp_fayl_yuklab, name="resp_fayl_yuklab"),
    path("respublika/fayllar/<int:pk>/ochirish/", views_resp.resp_fayl_ochirish, name="resp_fayl_ochirish"),
    path("royxat/", views.royxat, name="royxat"),
    path("xarita/", views.xarita, name="xarita"),
    path("xarita/api/", views.xarita_api, name="xarita_api"),
    path("yuklash/", views.yuklash, name="yuklash"),
    path("yuklash/holat/", views.yuklash_holat, name="yuklash_holat"),
    path("yuklash/<int:pk>/ochirish/", views.yuklama_ochirish, name="yuklama_ochirish"),
    path("brigadalar/", views.brigadalar, name="brigadalar"),
    path("brigadalar/yangi/<int:tuman_id>/", views.brigada_yangi, name="brigada_yangi"),
    path("brigadalar/<int:pk>/", views.brigada_tahrir, name="brigada_tahrir"),
    path("brigadalar/<int:pk>/ochirish/", views.brigada_ochirish, name="brigada_ochirish"),
    path("tp-kochirish/", views.tp_kochirish, name="tp_kochirish"),
    path("sozlamalar/", views_tg.sozlamalar, name="sozlamalar"),
    path("telegram/guruhlar/", views_tg.guruhlar, name="tg_guruhlar"),
    path("telegram/yuborish/", views_tg.yuborish, name="tg_yuborish"),
    path("telegram/holat/<int:pk>/", views_tg.holat, name="tg_holat"),
    path("foydalanuvchilar/", views.foydalanuvchilar, name="foydalanuvchilar"),
    path("foydalanuvchilar/yangi/", views.foydalanuvchi_tahrir, name="foydalanuvchi_yangi"),
    path("foydalanuvchilar/<int:pk>/", views.foydalanuvchi_tahrir, name="foydalanuvchi_tahrir"),
]
