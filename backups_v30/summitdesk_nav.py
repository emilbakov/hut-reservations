"""Hut-scoped navigation; never rely on caller-provided manager booleans."""
from django import template
from django.urls import reverse, NoReverseMatch
from floorplans.staff_tasks import access

register = template.Library()

@register.inclusion_tag('floorplans/includes/summitdesk_nav.html', takes_context=True)
def summitdesk_nav(context):
    request = context.get('request')
    if request is None:
        return {'visible': False}
    hut_id = (request.resolver_match.kwargs or {}).get('hut_id') if request.resolver_match else None
    if not hut_id or not request.user.is_authenticated:
        return {'visible': False}
    hut, manager, cleaner = access(request, hut_id)
    if not (manager or cleaner):
        return {'visible': False}
    name = request.resolver_match.url_name
    entries = [('staff_hub','Dashboard','⌂')]
    if manager:
        entries += [('staff_calendar','Reservations','▦'), ('staff_overview','Operations','◷'),
                    ('staff_housekeeping','Housekeeping','▣')]
    entries.append(('staff_tasks', 'Cleaning tasks' if manager else 'My tasks','✓'))
    if manager:
        entries += [('cleaner_team','Cleaning team','♙'), ('cleaner_invitations','Invitations','✉')]
    links=[]
    for route,label,symbol in entries:
        try:
            url=reverse('floorplans:'+route,args=[hut.pk])
        except NoReverseMatch:
            continue
        links.append({'url':url,'label':label,'symbol':symbol,'active':route==name})
    return {'visible': True,'hut':hut,'manager':manager,'links':links,'current':name}
