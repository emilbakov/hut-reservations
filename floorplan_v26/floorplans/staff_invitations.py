"""V26 manager invitations and public account activation."""
import hashlib
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .cleaner_invitations import CleanerInvitation
from .hut_staff import HutCleaner
from .staff_tasks import access


def _email_exists(email):
    User = get_user_model()
    return User.objects.filter(email__iexact=email).exists()


@login_required
@require_http_methods(['GET', 'POST'])
def cleaner_invitations(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers can invite cleaners')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'revoke':
            try:
                invite_id = int(request.POST.get('invite_id', ''))
            except (TypeError, ValueError):
                return HttpResponseBadRequest('Invalid invitation')
            CleanerInvitation.objects.filter(pk=invite_id, hut=hut, accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
            return redirect(request.path)
        if action != 'invite':
            return HttpResponseBadRequest('Invalid action')
        email = request.POST.get('email', '').strip().lower()
        from django.core.validators import validate_email
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Enter a valid email address.')
            return redirect(request.path)
        if _email_exists(email):
            messages.error(request, 'This email belongs to an existing account. Add that account from the cleaning team page instead.')
            return redirect(request.path)
        if CleanerInvitation.objects.filter(hut=hut, email__iexact=email, accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).exists():
            messages.error(request, 'An active invitation already exists for this email and hut. Revoke it first to resend.')
            return redirect(request.path)
        token, token_hash = CleanerInvitation.generate_token()
        invite = CleanerInvitation.objects.create(hut=hut, email=email, token_hash=token_hash, invited_by=request.user, expires_at=CleanerInvitation.expiry())
        link = request.build_absolute_uri(reverse('floorplans:cleaner_accept_invite', args=[token]))
        try:
            send_mail(
                subject=f'Invitation to join {hut.name} housekeeping',
                message=f'You have been invited to the housekeeping team at {hut.name}.\n\nCreate your cleaner account within 3 days:\n{link}\n\nIf you were not expecting this, ignore this message.',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            invite.delete()
            messages.error(request, 'Email could not be sent. Check your SMTP configuration and try again.')
            return redirect(request.path)
        messages.success(request, 'Invitation email sent.')
        return redirect(request.path)
    invitations = CleanerInvitation.objects.filter(hut=hut).select_related('invited_by')[:100]
    return render(request, 'floorplans/cleaner_invitations.html', {'hut': hut, 'invitations': invitations})


@require_http_methods(['GET', 'POST'])
def cleaner_accept_invite(request, token):
    if len(token) > 128 or len(token) < 20:
        return HttpResponseBadRequest('Invalid invitation link')
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    invitation = get_object_or_404(CleanerInvitation.objects.select_related('hut'), token_hash=token_hash)
    if not invitation.is_pending:
        return render(request, 'floorplans/cleaner_accept.html', {'invalid': True}, status=410)
    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
        else:
            User = get_user_model()
            username = request.POST.get('username', '').strip()
            if not username or len(username) > User._meta.get_field(User.USERNAME_FIELD).max_length:
                messages.error(request, 'Enter a valid username.')
            elif User.objects.filter(**{User.USERNAME_FIELD: username}).exists():
                messages.error(request, 'That username is already in use.')
            elif _email_exists(invitation.email):
                messages.error(request, 'An account with this email already exists. Ask your manager to add it directly.')
            else:
                candidate = User(**{User.USERNAME_FIELD: username, 'email': invitation.email})
                try:
                    validate_password(password1, user=candidate)
                    with transaction.atomic():
                        locked = CleanerInvitation.objects.select_for_update().get(pk=invitation.pk)
                        if not locked.is_pending or _email_exists(locked.email):
                            raise ValidationError('This invitation is no longer available.')
                        # This workflow supports the default Django username-based user model.
                        user = User.objects.create_user(**{User.USERNAME_FIELD: username}, email=locked.email, password=password1, is_staff=False)
                        HutCleaner.objects.get_or_create(hut=locked.hut, user=user)
                        locked.accepted_at = timezone.now()
                        locked.save(update_fields=['accepted_at'])
                except (ValidationError, IntegrityError, TypeError, ValueError) as exc:
                    messages.error(request, 'Account could not be created: ' + str(exc))
                else:
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('floorplans:staff_tasks', hut_id=invitation.hut_id)
    return render(request, 'floorplans/cleaner_accept.html', {'invitation': invitation})
