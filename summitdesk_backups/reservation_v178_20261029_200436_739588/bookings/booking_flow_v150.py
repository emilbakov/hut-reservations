"""Guest-facing feedback and hut information; inventory rules stay in services."""
import re

from django.utils.translation import gettext as _

from .public_profile_v149 import localized


def hut_information(hut):
    payment, payment_lang = localized(hut, "payment_instructions")
    reply, reply_lang = localized(hut, "reply_time")
    return {
        "hut": hut, "phone": hut.public_phone,
        "tel": re.sub(r"[^+0-9]", "", hut.public_phone),
        "email": hut.public_email,
        "directions": hut.directions_url if hut.directions_url.startswith(("https://", "http://")) else "",
        "payment": payment, "payment_lang": payment_lang,
        "reply": reply, "reply_lang": reply_lang,
    }


def error_summary(search, booking=None, party_error=""):
    result = []
    for form in (search, booking):
        if form is None or not form.is_bound:
            continue
        for name, errors in form.errors.items():
            field = form[name] if name in form.fields else None
            target = field.id_for_label if field and name != "contact_url" else ("rooms" if booking is form else "booking-dates")
            label = str(field.label) if field and name != "contact_url" else ""
            result.extend({"target": target, "label": label, "message": str(message)} for message in errors)
    if party_error and not booking:
        result.append({"target": "ph-search-guests", "label": _("Guests"), "message": party_error})
    return result


def receipt_context(reservation, *, staff=False):
    from django.utils import timezone
    huts = {}
    for item in reservation.items.all():
        if item.room.hut_id:
            huts.setdefault(item.room.hut_id, hut_information(item.room.hut))
    return {
        # Keep the public Karlak header, links and footer on every /r/<code>/ receipt,
        # including when a staff user opens the private reservation link.
        "reservation_base_template": "bookings/public_base_v124.html",
        "receipt_huts": list(huts.values()),
        "can_request_changes": reservation.status in reservation.HOLDING and reservation.check_in > timezone.localdate(),
    }
