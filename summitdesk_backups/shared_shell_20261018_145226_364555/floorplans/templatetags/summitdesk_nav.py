"""V30 hut-scoped nav, search, breadcrumbs, and nested active-section handling."""
from django import template
from django.urls import reverse, NoReverseMatch
from floorplans.staff_tasks import access

register = template.Library()

RESERVATION_ROUTES = {
    'staff_calendar', 'staff_arrivals', 'staff_new_booking', 'staff_reservation',
    'staff_reservation_edit', 'review_transfer', 'staff_transfer', 'staff_search',
}
OPERATIONS_ROUTES = {'staff_overview'}
HOUSEKEEPING_ROUTES = {'staff_housekeeping'}
TASK_ROUTES = {'staff_tasks'}
TEAM_ROUTES = {'cleaner_team'}
INVITATION_ROUTES = {'cleaner_invitations'}

@register.inclusion_tag('floorplans/includes/summitdesk_nav.html', takes_context=True)
def summitdesk_nav(context):
    request = context.get('request')
    if not request or not request.user.is_authenticated or not request.resolver_match:
        return {'visible': False}
    hut_id = request.resolver_match.kwargs.get('hut_id')
    if not hut_id:
        return {'visible': False}
    hut, manager, cleaner = access(request, hut_id)
    if not (manager or cleaner):
        return {'visible': False}
    name = request.resolver_match.url_name or ''
    section = ('staff_calendar' if name in RESERVATION_ROUTES else
               'staff_overview' if name in OPERATIONS_ROUTES else
               'staff_housekeeping' if name in HOUSEKEEPING_ROUTES else
               'staff_tasks' if name in TASK_ROUTES else
               'cleaner_team' if name in TEAM_ROUTES else
               'cleaner_invitations' if name in INVITATION_ROUTES else 'staff_hub')
    entries = [('staff_hub', 'Dashboard', '⌂')]
    if manager:
        entries += [('staff_calendar', 'Reservations', '▦'),
                    ('staff_overview', 'Operations', '◷'),
                    ('staff_housekeeping', 'Housekeeping', '▣')]
    entries += [('staff_tasks', 'Cleaning tasks' if manager else 'My tasks', '✓')]
    if manager:
        entries += [('cleaner_team', 'Cleaning team', '♙'),
                    ('cleaner_invitations', 'Invitations', '✉')]
    global_dashboard_url = reverse('bookings:dashboard') if request.user.is_staff else None
    links = []
    for route, label, symbol in entries:
        try:
            url = reverse('floorplans:' + route, args=[hut.pk])
        except NoReverseMatch:
            continue
        links.append({'url': url, 'label': label, 'symbol': symbol, 'active': route == section})
    try:
        search_url = reverse('floorplans:staff_search', args=[hut.pk]) if manager else None
    except NoReverseMatch:
        search_url = None
    active_label = next((x['label'] for x in links if x['active']), 'Dashboard')
    breadcrumb = None
    if name in RESERVATION_ROUTES and name not in ('staff_calendar', 'staff_search'):
        breadcrumb = {'label': 'Reservations', 'url': next((x['url'] for x in links if x['active']), None)}
    return {'visible': True, 'hut': hut, 'manager': manager, 'links': links,
            'current': name, 'active_label': active_label, 'breadcrumb': breadcrumb,
            'search_url': search_url, 'global_dashboard_url': global_dashboard_url}
