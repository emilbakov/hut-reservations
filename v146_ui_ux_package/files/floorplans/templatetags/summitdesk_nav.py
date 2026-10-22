"""SummitDesk shared staff navigation.

Presentation only. Never grants access to any endpoint; existing views remain
responsible for authentication, hut isolation, and write permissions.
"""
from urllib.parse import urlencode

from django import template
from django.urls import NoReverseMatch, reverse
from bookings.models import Hut
from floorplans.staff_tasks import access

register = template.Library()

BOOKINGS_STAFF = frozenset({
    'dashboard', 'dashboard_export', 'manager_reservations',
    'manager_reservation_action', 'manager_stays', 'manager_stay_action',
    'stay_history', 'stay_history_export', 'yearly_performance',
    'yearly_performance_export', 'manual_booking', 'room_calendar',
    'bed_management', 'reservation_payments', 'financial_dashboard',
    'financial_export', 'expense_dashboard', 'expense_export',
    'deposit_dashboard', 'lifecycle_dashboard', 'communications_dashboard',
    'conversation_inbox', 'conversation_thread', 'quick_replies',
    'guest_requests_dashboard', 'guest_link_controls',
    'approval_dashboard', 'manager_digest_preferences',
    'manager_digest_preview', 'manager_digest_history',
    'availability_calendar', 'calendar_create', 'calendar_edit',
    'calendar_timeline', 'calendar_move', 'notification_deliveries',
})

FRONT_DESK = {
    'staff_calendar': 'property_calendar', 'staff_arrivals': 'property_stays',
    'staff_new_booking': 'new', 'staff_reservation': 'reservations',
    'review_transfer': 'reservations', 'staff_search': 'reservations',
    'staff_history': 'reservations',
}
HUT_WORKSPACE = {
    'staff_hub': 'property', 'staff_overview': 'operations',
    'staff_housekeeping': 'housekeeping', 'staff_tasks': 'tasks',
    'cleaner_team': 'team', 'cleaner_invitations': 'invites',
    'staff_audit_dashboard': 'audit', 'staff_analytics': 'property_reports',
    'staff_financial_analytics': 'property_finances', 'visual_beds': 'beds',
    'bed_layout': 'beds', 'bed_manager': 'beds',
    'editor': 'beds', 'availability_map': 'beds',
    'availability': 'beds',
}
GLOBAL_WORKSPACE = {
    'dashboard': 'dashboard', 'calendar_timeline': 'calendar',
    'calendar_create': 'new', 'calendar_edit': 'reservations',
    'calendar_move': 'calendar', 'manager_reservations': 'reservations',
    'manager_reservation_action': 'reservations',
    'manager_stays': 'stays', 'manager_stay_action': 'stays',
    'manual_booking': 'new', 'room_calendar': 'beds',
    'bed_management': 'beds', 'availability_calendar': 'beds',
    'financial_dashboard': 'finances', 'financial_export': 'finances',
    'expense_dashboard': 'finances', 'expense_export': 'finances',
    'deposit_dashboard': 'finances', 'lifecycle_dashboard': 'finances',
    'reservation_payments': 'finances',
    'stay_history': 'reports', 'stay_history_export': 'reports',
    'yearly_performance': 'reports', 'yearly_performance_export': 'reports',
    'communications_dashboard': 'guests', 'guest_requests_dashboard': 'guests',
    'conversation_inbox': 'guests', 'conversation_thread': 'guests',
    'quick_replies': 'guests',
    'guest_link_controls': 'guests',
    'approval_dashboard': 'approvals', 'notification_deliveries': 'email_delivery',
    'manager_digest_preferences': 'reminders',
    'manager_digest_preview': 'reminders',
    'manager_digest_history': 'reminders',
}


def _match(request):
    if not request or not request.user.is_authenticated:
        return None
    match = getattr(request, 'resolver_match', None)
    if not match:
        return None
    if match.namespace == 'bookings' and match.url_name in BOOKINGS_STAFF:
        return match if request.user.is_staff else None
    if match.namespace == 'floorplans' and match.kwargs.get('hut_id'):
        return match
    return None


@register.simple_tag(takes_context=True)
def sd116_staff_area(context):
    """Only show management chrome on staff routes the user may access."""
    request = context.get('request')
    match = _match(request)
    if not match:
        return False
    if match.namespace == 'bookings':
        return True
    hut, manager, cleaner = access(request, match.kwargs['hut_id'])
    return bool(manager or cleaner)


def _url(namespace, name, hut_id=None, slug=None):
    try:
        url = reverse(namespace + ':' + name, args=[hut_id] if hut_id else [])
    except NoReverseMatch:
        return None
    if namespace == 'bookings' and slug:
        return url + '?' + urlencode({'hut': slug})
    return url


def _link(namespace, route, label, icon, key, current, hut_id=None, slug=None):
    url = _url(namespace, route, hut_id=hut_id, slug=slug)
    if not url:
        return None
    return {'url': url, 'label': label, 'icon': icon, 'active': key == current, 'key': key}


@register.inclusion_tag('floorplans/includes/summitdesk_nav.html', takes_context=True)
def summitdesk_nav(context):
    request = context.get('request')
    match = _match(request)
    if not match:
        return {'visible': False}

    user = request.user
    hut = None
    manager = False
    cleaner = False
    allowed_huts = []
    if match.namespace == 'floorplans':
        hut, manager, cleaner = access(request, match.kwargs['hut_id'])
        if not (manager or cleaner):
            return {'visible': False}
    if user.is_staff:
        allowed_huts = list(
            Hut.objects.filter(
                is_active=True,
                managers=user,
            ).order_by('name').distinct()
        )
        if not hut:
            selected_slug = context.get('selected_slug') or request.GET.get('hut', '')
            hut = next((h for h in allowed_huts if h.slug == selected_slug), None)
            if not hut and len(allowed_huts) == 1:
                hut = allowed_huts[0]
        if hut:
            manager = user.is_superuser or any(h.pk == hut.pk for h in allowed_huts)

    section = (GLOBAL_WORKSPACE.get(match.url_name, 'dashboard')
               if match.namespace == 'bookings' else
               FRONT_DESK.get(match.url_name, HUT_WORKSPACE.get(match.url_name, 'property')))
    groups = []

    def group(title, entries):
        links = [link for link in entries if link]
        if links:
            groups.append({'title': title, 'links': links})

    def b(route, label, icon, key):
        return _link('bookings', route, label, icon, key, section,
                     slug=hut.slug if hut else None) if user.is_staff else None

    def f(route, label, icon, key):
        return _link('floorplans', route, label, icon, key, section, hut_id=hut.pk) if hut and manager else None

    if user.is_staff:
        group('Front desk', [
            b('dashboard', 'Overview', 'layout-dashboard', 'dashboard'),
            b('calendar_timeline', 'Weekly reservation calendar', 'calendar-days', 'calendar'),
            b('manager_reservations', 'Reservations', 'book-open', 'reservations'),
            b('manager_stays', 'Arrivals & departures', 'arrow-left-right', 'stays'),
        ])
    if hut and manager:
        group('Property operations', [
            f('staff_hub', 'Property dashboard', 'house', 'property'),
            f('staff_calendar', 'Monthly stay planner', 'calendar-range', 'property_calendar'),
            f('staff_arrivals', 'Property arrivals', 'arrow-left-right', 'property_stays'),
            f('staff_overview', 'Daily operations', 'clipboard-list', 'operations'),
            f('visual_beds', 'Rooms & beds', 'bed-double', 'beds'),
            f('staff_housekeeping', 'Housekeeping', 'sparkles', 'housekeeping'),
            f('staff_tasks', 'Cleaning tasks', 'list-checks', 'tasks'),
        ])
        group('Property insights', [
            f('staff_analytics', 'Occupancy analytics', 'chart-no-axes-column', 'property_reports'),
            f('staff_financial_analytics', 'Booking value', 'wallet', 'property_finances'),
            f('staff_audit_dashboard', 'Audit trail', 'clipboard-list', 'audit'),
        ])
        group('Property team', [
            f('cleaner_team', 'Cleaning team', 'users', 'team'),
            f('cleaner_invitations', 'Invitations', 'mail', 'invites'),
        ])
    elif hut and cleaner:
        group('Your workspace', [
            _link('floorplans', 'staff_hub', 'My dashboard', 'house', 'property', section, hut_id=hut.pk),
            _link('floorplans', 'staff_tasks', 'My cleaning tasks', 'list-checks', 'tasks', section, hut_id=hut.pk),
        ])
    if user.is_staff:
        group('Business', [
            b('financial_dashboard', 'Finances', 'wallet', 'finances'),
            b('stay_history', 'Reports & history', 'chart-no-axes-column', 'reports'),
            b('communications_dashboard', 'Guest communication', 'messages-square', 'guests'),
            b('conversation_inbox', 'Guest inbox', 'mail', 'guests'),
            b('approval_dashboard', 'Guest approvals', 'clipboard-list', 'approvals'),
            b('notification_deliveries', 'Email delivery', 'mail', 'email_delivery'),
            b('manager_digest_preferences', 'Reminder settings', 'mail', 'reminders'),
        ])

    if user.is_superuser:
        group('Administration', [{'url': reverse('admin:index'), 'label': 'Django admin', 'icon': 'settings', 'active': False, 'key': 'admin'}])

    current_link = next((link for g in groups for link in g['links'] if link['active']), None)
    title = current_link['label'] if current_link else 'Workspace'
    if match.url_name in ('staff_new_booking', 'manual_booking', 'calendar_create'):
        title = 'New reservation'
    if match.url_name in ('staff_reservation', 'calendar_edit'):
        title = 'Reservation details'
    if match.url_name == 'staff_search':
        title = 'Search reservations'
    search_url = (f('staff_search', 'Search', 'search', 'reservations') or {}).get('url') if manager and hut else None
    if not search_url and user.is_staff:
        search_url = b('manager_reservations', 'Search', 'search', 'reservations')['url']
    property_options = [{'name': h.name, 'url': _url('floorplans', 'staff_hub', hut_id=h.pk),
                         'selected': bool(hut and hut.pk == h.pk)} for h in allowed_huts]
    if hut and cleaner and not manager:
        property_options = [{'name': hut.name, 'url': _url('floorplans', 'staff_hub', hut_id=hut.pk), 'selected': True}]
    return {
        'visible': True, 'groups': groups, 'title': title, 'hut': hut,
        'role': 'Manager' if manager else 'Cleaner', 'search_url': search_url,
        'property_options': property_options, 'user': user,
        'dashboard_url': _url('bookings', 'dashboard') if user.is_staff else _url('floorplans', 'staff_hub', hut_id=hut.pk),
        'new_booking_url': (_url('floorplans', 'staff_new_booking', hut_id=hut.pk) if hut and manager else _url('bookings', 'manual_booking')) if user.is_staff else None,
        'public_url': _url('bookings', 'hut_list'),
    }
