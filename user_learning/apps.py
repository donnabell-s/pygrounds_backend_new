from django.apps import AppConfig


class UserLearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_learning'

    def ready(self):
        pass  # history snapshots written explicitly; no signals needed
