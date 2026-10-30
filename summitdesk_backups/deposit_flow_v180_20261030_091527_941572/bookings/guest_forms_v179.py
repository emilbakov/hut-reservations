"""Presentation and validation for manager-reviewed guest requests."""
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GuestChangeForm(forms.Form):
    request_type = forms.ChoiceField(label=_("Request type"), choices=[
        ('change', _("Change dates / booking")), ('cancellation', _("Request cancellation"))],
        widget=forms.Select(attrs={'id': 'gss-request-type'}))
    requested_check_in = forms.DateField(label=_("Requested arrival (for changes)"), required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'id': 'gss-check-in'}))
    requested_check_out = forms.DateField(label=_("Requested departure (for changes)"), required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'id': 'gss-check-out'}))
    details = forms.CharField(label=_("Additional details"), required=False, max_length=2000,
        widget=forms.Textarea(attrs={'id': 'gss-details', 'rows': 4,
            'placeholder': _("Tell the hut manager what you'd like to change or why you need to cancel.")}))

    def __init__(self, data=None, *args, **kwargs):
        # Cancellation requests ignore date inputs, including stale or invalid
        # values from a previously selected change request, as the old view did.
        if data is not None and data.get('request_type') == 'cancellation':
            data = data.copy()
            data['requested_check_in'] = data['requested_check_out'] = ''
        super().__init__(data, *args, **kwargs)
        for name in ['requested_check_in', 'requested_check_out']:
            self.fields[name].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean(self):
        values = super().clean()
        if values.get('request_type') != 'change':
            return values
        start, end = values.get('requested_check_in'), values.get('requested_check_out')
        if start is None and 'requested_check_in' not in self.errors:
            self.add_error('requested_check_in', _("Choose an arrival date."))
        if end is None and 'requested_check_out' not in self.errors:
            self.add_error('requested_check_out', _("Choose a departure date."))
        if start and start < timezone.localdate():
            self.add_error('requested_check_in', _("Arrival cannot be in the past."))
        if start and end and end <= start:
            self.add_error('requested_check_out', _("Departure must be after arrival."))
        return values

    def mark_errors(self):
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs['aria-invalid'] = 'true'
                widget.attrs['aria-describedby'] = widget.attrs['id'] + '-errors'
