from django.apps import AppConfig


class AchievementsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'achievements'

    def ready(self):
        # import signal handlers
        try:
            import achievements.signals  # noqa: F401
        except Exception:
            pass
