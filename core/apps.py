from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Hodimlar nazorati"

    def ready(self):
        from django.contrib.auth.models import User
        from django.db.models.signals import post_save

        from .models import Profil

        def yarat(sender, instance, created, **kw):
            if created:
                Profil.objects.get_or_create(user=instance, defaults={"rol": "admin" if instance.is_superuser else "tuman_hodim"})

        post_save.connect(yarat, sender=User, weak=False, dispatch_uid="core_profil_yarat")
