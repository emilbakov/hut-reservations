"""Public presentation settings and policy pages; no booking permissions change."""
import re

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import get_language, gettext as _

from .models import PublicWebsiteSettings


def profile_for(request):
    if not hasattr(request, "_public_profile_v149"):
        request._public_profile_v149 = PublicWebsiteSettings.objects.filter(pk=1).first() or PublicWebsiteSettings()
    return request._public_profile_v149


def localized(profile, field):
    lang = "bg" if (get_language() or "en").startswith("bg") else "en"
    value = getattr(profile, field + "_" + lang)
    if value.strip():
        return value, lang
    fallback = "en" if lang == "bg" else "bg"
    return getattr(profile, field + "_" + fallback), fallback


def public_context(request):
    profile = profile_for(request)
    configured_name = settings.HUT_NAME.strip()
    brand = profile.brand_name.strip() or (configured_name if configured_name != "Mountain Hut" else "SummitDesk")
    address, address_lang = localized(profile, "address")
    hero_alt, _lang = localized(profile, "hero_alt")
    # Metadata for a private link must never echo its path, code or query string.
    match = request.resolver_match
    public_route = match and match.url_name in {"public_home", "hut_list", "hut_detail", "public_policy"}
    canonical_path = request.path if public_route else reverse("bookings:public_home")
    return {
        "HUT_NAME": brand,
        "PUBLIC149": {
            "brand": brand,
            "phone": profile.contact_phone,
            "tel": re.sub(r"[^+0-9]", "", profile.contact_phone),
            "email": profile.contact_email,
            "address": address,
            "address_lang": address_lang,
            "map_url": profile.map_url if profile.map_url.startswith(("https://", "http://")) else "",
            "privacy": profile.privacy_published and bool(profile.privacy_en.strip() or profile.privacy_bg.strip()),
            "cancellation": profile.cancellation_published and bool(profile.cancellation_en.strip() or profile.cancellation_bg.strip()),
            "hero_url": profile.hero_image.url if profile.hero_image else "",
            "hero_width": profile.hero_width,
            "hero_height": profile.hero_height,
            "hero_alt": hero_alt,
            "canonical": request.build_absolute_uri(canonical_path),
            "social_image": request.build_absolute_uri(static("bookings/social-v149.jpg")),
            "description": _("Discover mountain huts, explore rooms and check real bed availability for your next mountain stay."),
            "private": not public_route,
            "locale": "bg_BG" if (get_language() or "en").startswith("bg") else "en_GB",
        },
    }


def public_policy(request, kind):
    if kind not in {"privacy", "cancellation"}:
        raise Http404
    profile = profile_for(request)
    text, lang = localized(profile, kind)
    if not getattr(profile, kind + "_published") or not text.strip():
        raise Http404
    return render(request, "bookings/public_policy_v149.html", {
        "policy_title": _("Privacy notice") if kind == "privacy" else _("Cancellation policy"),
        "policy_text": text, "policy_lang": lang,
        "policy_fallback": not (get_language() or "en").startswith(lang),
        "policy_operator": profile.operator_name,
        "policy_email": (profile.privacy_email or profile.contact_email) if kind == "privacy" else profile.contact_email,
        "policy_updated": profile.updated_at,
    })
