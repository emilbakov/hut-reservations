"""Install expenses without replacing the existing payment or finance modules."""
from pathlib import Path
from shutil import copy2

models = Path("bookings/models.py")
urls = Path("bookings/urls.py")
finance_template = Path("bookings/templates/bookings/financial_dashboard.html")
for file in (models, urls, finance_template):
    if not file.is_file():
        raise SystemExit(f"Missing {file}. Run from the project root after installing Financial Reports.")
if "class PaymentTransaction(models.Model):" not in models.read_text():
    raise SystemExit("Install Payment Management first.")
if "name='financial_dashboard'" not in urls.read_text():
    raise SystemExit("Install Financial Dashboard first.")
if "class HutExpense(models.Model):" not in models.read_text():
    backup = models.with_name(models.name + ".before_expenses")
    if not backup.exists(): copy2(models, backup)
    models.write_text(models.read_text().rstrip() + "\n" + Path("expense_model.txt").read_text())
if "name='expense_dashboard'" not in urls.read_text():
    backup = urls.with_name(urls.name + ".before_expenses")
    if not backup.exists(): copy2(urls, backup)
    urls.write_text(urls.read_text().rstrip() + """

# Hut expense management and CSV export
from .expenses import expense_dashboard, expense_export
urlpatterns += [
    path('staff/expenses/', expense_dashboard, name='expense_dashboard'),
    path('staff/expenses/export/', expense_export, name='expense_export'),
]
""")
if "bookings:expense_dashboard" not in finance_template.read_text():
    backup = finance_template.with_name(finance_template.name + ".before_expenses")
    if not backup.exists(): copy2(finance_template, backup)
    source = finance_template.read_text()
    source = source.replace("{% block content %}", """{% block content %}
<p><a href="{% url 'bookings:expense_dashboard' %}">Expenses &amp; cash flow →</a></p>""", 1)
    finance_template.write_text(source)
print("Installed expense model, URLs and financial dashboard link.")
print("Next: python manage.py makemigrations bookings && python manage.py migrate")
