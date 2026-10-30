"""Publication, privacy and guest-navigation regressions for the public polish."""
from datetime import timedelta
from html.parser import HTMLParser
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Room, PublicWebsiteSettings
from .self_service import issue_guest_link
from .services import create_reservation


class HeadParser(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.meta = {}
        self.links = {}
        self.feed(content.split("</head>")[0])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", ""))] = attrs.get("content", "")
        if tag == "link":
            self.links[attrs.get("rel")] = attrs.get("href", "")


class PublicPolishV149Tests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name="Pine Hut", slug="pine-hut")
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=4, price_per_night="12.00")
        self.url = reverse("bookings:public_home")
        self.detail = reverse("bookings:hut_detail", args=[self.hut.slug])

    def profile(self, **kwargs):
        return PublicWebsiteSettings.objects.create(**kwargs)

    @override_settings(HUT_NAME="Mountain Hut")
    def test_guest_header_has_no_staff_login_and_default_brand_is_summitdesk(self):
        for url in (self.url, self.detail, reverse("bookings:book")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                header = html.split("<header", 1)[1].split("</header>", 1)[0]
                self.assertNotIn(reverse("bookings:staff_login"), header)
                self.assertIn(reverse("bookings:staff_login"), html.split("<footer", 1)[1])
                self.assertContains(response, "SummitDesk")

    @override_settings(HUT_NAME="Existing Custom Brand")
    def test_custom_environment_brand_is_preserved_and_admin_can_override_it(self):
        self.assertContains(self.client.get(self.url), "Existing Custom Brand")
        self.profile(brand_name="Trail &amp; Lodge")
        self.assertContains(self.client.get(self.url), "Trail &amp;amp; Lodge")

    def test_high_priority_responsive_hero_and_complete_absolute_social_metadata(self):
        response = self.client.get(self.url, {"email": "private@example.com"}, secure=True)
        html = response.content.decode()
        head = HeadParser(html)
        self.assertContains(response, 'fetchpriority="high"')
        self.assertContains(response, 'width="1920" height="1080"')
        self.assertContains(response, 'hero-v149-2560.avif')
        self.assertIn("icon", head.links)
        self.assertEqual(head.meta["og:image:width"], "1200")
        self.assertEqual(head.meta["og:image:height"], "630")
        self.assertTrue(head.meta["og:image"].startswith("https://testserver/static/"))
        self.assertEqual(head.meta["og:url"], "https://testserver/")
        self.assertEqual(head.links["canonical"], "https://testserver/")
        self.assertNotIn("private@example.com", str(head.meta))
        self.assertEqual(head.meta["twitter:card"], "summary_large_image")

    def test_private_booking_codes_and_tokens_never_enter_metadata(self):
        start = timezone.localdate() + timedelta(days=8)
        reservation = create_reservation(check_in=start, check_out=start + timedelta(days=2),
            beds_by_room={self.room.pk: 1}, name="Private Guest", email="private@example.com")
        portal = issue_guest_link(reservation)
        for url in (reservation.get_absolute_url(), portal):
            with self.subTest(url=url):
                response = self.client.get(url, {"private": "sensitive-query"})
                self.assertEqual(response.status_code, 200)
                head = HeadParser(response.content.decode())
                self.assertEqual(head.meta["robots"], "noindex, nofollow, noarchive")
                self.assertNotIn("canonical", head.links)
                values = str(head.meta)
                for secret in (reservation.code, portal, "sensitive-query", reservation.email):
                    self.assertNotIn(secret, values)
                self.assertEqual(head.meta["og:url"], "http://testserver/")

    def test_unpublished_policies_and_empty_contacts_are_not_advertised(self):
        self.profile(privacy_en="A private draft", cancellation_bg="Непубликувана чернова")
        html = self.client.get(self.url).content.decode()
        for kind in ("privacy", "cancellation"):
            url = reverse("bookings:public_policy", args=[kind])
            self.assertNotIn(url, html)
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotIn("A private draft", html)
        self.assertNotIn('href="tel:', html)
        self.assertNotIn('href="mailto:', html)

    def test_publication_requires_operator_text_and_privacy_contact(self):
        p = PublicWebsiteSettings(privacy_published=True, cancellation_published=True)
        with self.assertRaises(ValidationError) as caught:
            p.full_clean()
        self.assertTrue({"operator_name", "privacy_en", "cancellation_en", "privacy_email"}.issubset(caught.exception.message_dict))
        p.operator_name = "Example Operator"
        p.privacy_email = "privacy@example.com"
        p.privacy_en = "Reviewed notice"
        p.cancellation_en = "Reviewed terms"
        p.full_clean()

    def test_published_policies_are_escaped_and_linked_where_details_are_collected(self):
        self.profile(operator_name="Example Operator", privacy_email="privacy@example.com",
            privacy_en='<script>alert("x")</script>\n\nReviewed privacy notice', privacy_published=True,
            cancellation_en="Reviewed cancellation terms", cancellation_published=True)
        url = reverse("bookings:public_policy", args=["privacy"])
        response = self.client.get(url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "Example Operator")
        self.assertContains(response, 'mailto:privacy@example.com')
        start = timezone.localdate() + timedelta(days=8)
        response = self.client.get(self.detail, {"check_in": start.isoformat(), "check_out": (start + timedelta(days=2)).isoformat()})
        self.assertContains(response, "How we use your booking details")
        self.assertContains(response, url)

    def test_bulgarian_public_shell_policy_and_contact_fallback(self):
        self.profile(operator_name="Example Operator", contact_email="hello@example.com", contact_phone="+359 888 123 456",
            address_en="Rhodope Mountains", address_bg="Родопите", map_url="https://www.openstreetmap.org/",
            privacy_en="English reviewed text", privacy_bg="Прегледан текст на български", privacy_published=True)
        self.client.cookies["django_language"] = "bg"
        response = self.client.get(reverse("bookings:public_policy", args=["privacy"]))
        self.assertContains(response, 'lang="bg"')
        self.assertContains(response, "Прегледан текст на български")
        self.assertContains(response, "Родопите")
        self.assertNotContains(response, "English reviewed text")
        self.assertContains(response, 'href="tel:+359888123456"')
        self.assertContains(response, "Често задавани въпроси")
        p = PublicWebsiteSettings.objects.get()
        p.privacy_bg = ""
        p.save()
        response = self.client.get(reverse("bookings:public_policy", args=["privacy"]))
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, "English reviewed text")
        self.assertContains(response, "pub149-policy-fallback")

    def test_unsafe_map_urls_phone_markup_and_tiny_custom_hero_are_rejected(self):
        for value in ("javascript:alert(1)", "ftp://example.com/map"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PublicWebsiteSettings(map_url=value).full_clean()
        with self.assertRaises(ValidationError):
            PublicWebsiteSettings(contact_phone='123\" onclick="alert(1)').full_clean()
        stream = BytesIO()
        Image.new("RGB", (640, 400)).save(stream, "JPEG")
        p = PublicWebsiteSettings(hero_image=SimpleUploadedFile("tiny.jpg", stream.getvalue(), content_type="image/jpeg"), hero_alt_en="A landscape")
        with self.assertRaises(ValidationError) as caught:
            p.full_clean()
        self.assertIn("hero_image", caught.exception.message_dict)

    def test_public_settings_admin_is_superuser_only_even_with_model_permissions(self):
        from django.contrib.auth.models import Permission
        ordinary = get_user_model().objects.create_user("public-editor", is_staff=True)
        ordinary.user_permissions.add(*Permission.objects.filter(content_type__model="publicwebsitesettings"))
        self.client.force_login(ordinary)
        url = reverse("admin:bookings_publicwebsitesettings_add")
        self.assertEqual(self.client.get(url).status_code, 403)
        owner = get_user_model().objects.create_superuser("public-owner", "owner@example.com", "test")
        self.client.force_login(owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.profile()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:bookings_publicwebsitesettings_change", args=[1])).status_code, 200)
