"""Optional ready hook for V31. See INSTALL_V31.md for wiring."""
from django.apps import AppConfig

class FloorplansV31Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'floorplans'

    def ready(self):
        from . import reservation_audit
        reservation_audit.register_optional_signals()
