"""Hut-scoped expense ledger and cash-flow report."""
import csv
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET
from .models import Hut, HutExpense
from .financial_reports import report_scope, summary_for

ZERO = Decimal('0.00')

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = HutExpense
        fields = ['category', 'expense_date', 'amount', 'description', 'reference']
        widgets = {'expense_date': forms.DateInput(attrs={'type': 'date'}),
                   'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})}

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if not amount.is_finite() or amount <= 0:
            raise forms.ValidationError('Enter a positive expense amount.')
        return amount

    def clean_expense_date(self):
        day = self.cleaned_data['expense_date']
        if not 2000 <= day.year <= 2100:
            raise forms.ValidationError('Expense date is outside the supported range.')
        return day


def allowed_huts(user):
    return Hut.objects.all() if user.is_superuser else Hut.objects.filter(managers=user)


def expense_scope(request):
    scope = report_scope(request)
    if scope is None:
        return None
    first, end, huts, selected, slug, allowed = scope
    # No cross-hut access: managers with multiple huts are scoped by
    # permitted_hut_selection to one selected hut.
    permitted = allowed_huts(request.user)
    if selected:
        permitted = permitted.filter(pk=selected.pk)
    return first, end, huts, selected, slug, allowed, permitted


def expense_summary(request):
    scope = expense_scope(request)
    if scope is None:
        return None
    first, end, huts, selected, slug, allowed, permitted = scope
    expenses = HutExpense.objects.filter(
        hut__in=permitted, expense_date__gte=first, expense_date__lt=end
    ).select_related('hut', 'recorded_by').order_by('-expense_date', '-pk')
    totals = expenses.aggregate(total=Coalesce(Sum('amount'), Value(ZERO), output_field=DecimalField(max_digits=14, decimal_places=2)))
    categories = list(expenses.values('category').annotate(total=Sum('amount')).order_by('category'))
    labels = dict(HutExpense.Category.choices)
    for category in categories:
        category['label'] = labels.get(category['category'], category['category'])
    cash = summary_for(first, end, allowed)
    return {
        'month': first, 'next': end, 'previous': first-timedelta(days=1),
        'huts': huts, 'selected_hut': selected, 'selected_slug': slug,
        'manager_mode': not request.user.is_superuser,
        'month_options': [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        'expenses': expenses, 'expense_total': totals['total'], 'categories': categories,
        'net_cash': cash['net_cash'], 'net_after_expenses': cash['net_cash']-totals['total'],
        'receipts': cash['receipts'], 'refunds': cash['refunds'],
        'currency': settings.BOOKING_CURRENCY,
    }


@staff_member_required
@require_http_methods(['GET', 'POST'])
def expense_dashboard(request):
    data = expense_summary(request)
    if data is None:
        return HttpResponseBadRequest('Invalid report month.')
    selected = data['selected_hut']
    if request.method == 'POST':
        hut_id = request.POST.get('hut_id', '')
        if not hut_id.isdecimal():
            return HttpResponseBadRequest('Choose a hut for the expense.')
        hut = get_object_or_404(allowed_huts(request.user), pk=int(hut_id))
        # A selected hut may not be bypassed by posting a different hut ID.
        if selected is not None and hut.pk != selected.pk:
            return HttpResponseBadRequest('Hut does not match selected report.')
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.hut = hut
            expense.recorded_by = request.user
            with transaction.atomic():
                expense.save()
            messages.success(request, 'Expense recorded.')
            return redirect(f'{request.path}?hut={hut.slug}&year={data["month"].year}&month={data["month"].month}')
    else:
        form = ExpenseForm(initial={'expense_date': timezone.localdate()})
    data['form'] = form
    data['allowed_huts'] = allowed_huts(request.user) if selected is None else allowed_huts(request.user).filter(pk=selected.pk)
    return render(request, 'bookings/expenses.html', data)


@staff_member_required
@require_GET
def expense_export(request):
    data = expense_summary(request)
    if data is None:
        return HttpResponseBadRequest('Invalid report month.')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="expenses-{data["month"]:%Y-%m}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Expense date', 'Hut', 'Category', 'Amount', 'Currency', 'Description', 'Reference', 'Recorded by'])
    def safe(value):
        value = str(value or '')
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    for expense in data['expenses']:
        writer.writerow([expense.expense_date, safe(expense.hut.name), expense.get_category_display(),
                         expense.amount, settings.BOOKING_CURRENCY, safe(expense.description),
                         safe(expense.reference), safe(expense.recorded_by)])
    writer.writerow([])
    writer.writerow(['Metric', 'Amount', 'Currency'])
    for label, key in [('Payments and deposits received', 'receipts'), ('Refunds', 'refunds'),
                       ('Net cash received', 'net_cash'), ('Expenses', 'expense_total'),
                       ('Net cash after expenses', 'net_after_expenses')]:
        writer.writerow([label, data[key], settings.BOOKING_CURRENCY])
    return response
