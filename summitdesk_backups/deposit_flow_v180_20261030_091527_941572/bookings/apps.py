from django.apps import AppConfig


class BookingsConfig(AppConfig):
    name = "bookings"

    def ready(self):
        from .login_guard_v151 import register_signals
        register_signals()
