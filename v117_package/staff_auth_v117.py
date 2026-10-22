"""SummitDesk staff sign-in, sign-out and legacy staff-login routing.

Authentication remains Django's session authentication. Access is limited to
users assigned to active huts as managers or cleaners, plus superusers.
No new permissions are granted by this module.
"""
from urllib.parse import urlencode, urlsplit

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from bookings.models import Hut
from floorplans.hut_staff import HutCleaner


def staff_role(user):
    """Return the active role; do not equate is_staff with hut authorization."""
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        return 'manager'
    if Hut.objects.filter(is_active=True, managers=user).exists():
        return 'manager'
    if HutCleaner.objects.filter(hut__is_active=True, user=user).exists():
        return 'cleaner'
    return None


class StaffAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'autocomplete': 'username', 'autofocus': True, 'placeholder': 'Your username',
        'class': 'sd117-input', 'spellcheck': 'false',
    }))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={
        'autocomplete': 'current-password', 'placeholder': 'Enter your password',
        'class': 'sd117-input', 'id': 'sd117-password',
    }))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if staff_role(user) is None:
            raise ValidationError(
                'Unable to sign in. Check your details or ask your manager for access.',
                code='no_staff_access',
            )


class StaffLoginView(LoginView):
    template_name = 'bookings/staff_login.html'
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = False

    def get(self, request, *args, **kwargs):
        if staff_role(request.user):
            return HttpResponseRedirect(self.get_success_url())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['signed_in_without_access'] = (
            self.request.user.is_authenticated and not staff_role(self.request.user)
        )
        return context

    def get_success_url(self):
        # Preserve only local staff destinations. Never send a login to an
        # arbitrary external URL, an admin URL, or back to the login page.
        role = staff_role(self.request.user)
        target = self.request.POST.get('next') or self.request.GET.get('next') or ''
        if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            parsed = urlsplit(target)
            if (not parsed.netloc and parsed.path.startswith('/staff/')
                    and parsed.path not in ('/staff/login/', '/staff/logout/')
                    and (self.request.user.is_staff and role == 'manager'
                         or parsed.path.startswith('/staff/floorplans/'))):
                return target
        if role == 'manager' and self.request.user.is_staff:
            return reverse('bookings:dashboard')
        return reverse('floorplans:staff_home')

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.POST.get('remember_me'):
            self.request.session.set_expiry(0)
        return response


class StaffLogoutView(LogoutView):
    next_page = 'bookings:staff_login'


class StaffLoginRedirectMiddleware:
    """Redirect old @staff_member_required login prompts to SummitDesk.

    Django's staff_member_required hardcodes admin:login; only a request to
    /admin/login/ with a local /staff/ destination is redirected. Normal
    Django admin sign-in remains available at /admin/login/.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('GET', 'HEAD') and request.path == '/admin/login/':
            target = request.GET.get('next', '')
            parsed = urlsplit(target)
            if (not parsed.scheme and not parsed.netloc
                    and parsed.path.startswith('/staff/')
                    and parsed.path not in ('/staff/login/', '/staff/logout/')):
                return HttpResponseRedirect('/staff/login/?' + urlencode({'next': target}))
        return self.get_response(request)
