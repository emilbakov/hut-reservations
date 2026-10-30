from decimal import Decimal
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DepositApprovalForm(forms.Form):
    deposit_amount = forms.DecimalField(label=_("Required deposit"), max_digits=12, decimal_places=2,
        min_value=0, widget=forms.NumberInput(attrs={'min': '0', 'step': '.01'}))
    deposit_due_at = forms.DateTimeField(label=_("Deposit deadline (hut local time)"), required=False,
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))
    instructions_en = forms.CharField(label=_("Payment instructions (English)"), required=False, max_length=4000,
                                      widget=forms.Textarea(attrs={'rows': 3}))
    instructions_bg = forms.CharField(label=_("Payment instructions (Bulgarian)"), required=False, max_length=4000,
                                      widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, reservation, data=None, **kwargs):
        from .deposit_flow_v180 import default_terms
        self.reservation = reservation
        kwargs.setdefault('initial', default_terms(reservation))
        kwargs.setdefault('auto_id', f'deposit-{reservation.pk}-%s')
        super().__init__(data, **kwargs)

    def clean(self):
        from .payments import balance
        from datetime import datetime, time
        values = super().clean()
        amount = values.get('deposit_amount')
        due = values.get('deposit_due_at')
        if amount is not None and amount > Decimal(self.reservation.total_price):
            self.add_error('deposit_amount', _('The deposit cannot exceed the booking total.'))
        if amount and (not due or due <= timezone.now() or due > timezone.make_aware(
                datetime.combine(self.reservation.check_in, time(23, 59, 59)))):
            self.add_error('deposit_due_at', _('Choose a future deadline no later than the end of the arrival day.'))
        if amount is not None and amount > balance(self.reservation)['net'] and not (
                values.get('instructions_en') or values.get('instructions_bg')):
            self.add_error('instructions_en', _('Enter actual payment instructions in at least one language.'))
        if amount == 0:
            values['deposit_due_at'] = timezone.now()
        return values
