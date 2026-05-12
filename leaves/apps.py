from django.apps import AppConfig


class LeavesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leaves'
    verbose_name = 'Διαχείριση Αδειών'

    def ready(self):
        """Register signals"""
        import leaves.signals  # noqa