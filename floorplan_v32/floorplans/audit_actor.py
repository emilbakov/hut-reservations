"""Request-scoped actor for synchronous Django signals (no global mutable state)."""
from contextvars import ContextVar

_actor = ContextVar('summitdesk_audit_actor', default=None)


def current_actor():
    return _actor.get()


class ReservationAuditActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        token = _actor.set(user if user is not None and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            _actor.reset(token)
