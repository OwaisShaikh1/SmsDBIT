from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sms'

    def ready(self):
        import sms.signals  # Register signals when app is ready
