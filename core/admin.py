from django.contrib import admin

from .models import TP, Brigada, Hodim, Profil, Tuman, Yuklama


@admin.register(Tuman)
class TumanAdmin(admin.ModelAdmin):
    list_display = ("nom", "qisqa", "tartib")
    list_editable = ("qisqa", "tartib")


class HodimInline(admin.TabularInline):
    model = Hodim
    extra = 1


@admin.register(Brigada)
class BrigadaAdmin(admin.ModelAdmin):
    list_display = ("nom", "tuman", "raqam")
    list_filter = ("tuman",)
    search_fields = ("nom", "manba")
    inlines = [HodimInline]


@admin.register(TP)
class TPAdmin(admin.ModelAdmin):
    list_display = ("raqam", "feeder", "podstansiya", "tuman", "brigada")
    list_filter = ("tuman",)
    search_fields = ("raqam", "feeder", "podstansiya")
    raw_id_fields = ("brigada",)


@admin.register(Yuklama)
class YuklamaAdmin(admin.ModelAdmin):
    list_display = ("tur", "sana", "holat", "qatorlar", "yuklagan", "vaqt")
    list_filter = ("tur", "holat")


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "tuman")
    list_filter = ("rol",)
