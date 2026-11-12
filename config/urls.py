from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Hodimlar nazorati - boshqaruv"
admin.site.site_title = "Hodimlar nazorati"
admin.site.index_title = "Ma'lumotlar bazasi"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]
