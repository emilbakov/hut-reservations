"""Django-translated browser messages, serialized with json_script."""
from django.utils.translation import gettext

MESSAGES = ('Choose beds to see the total', '%(selected)s of %(target)s beds', '%(selected)s of %(target)s beds selected. Choose %(remaining)s more.', 'All %(target)s beds selected. Review your details and send the request.', 'Arrival', 'Arrival: %(date)s · choose departure', 'Arrival: %(date)s. Choose a later departure in this room.', 'Availability updated. Review your beds.', 'Available alternatives — your guest details are kept:', 'Available for %(count)s %(unit)s · checkout is not charged.', 'Check your dates.', 'Checking availability. Your guest details are kept.', 'Choose a room', 'Choose a room or click an available arrival.', 'Choose a stay of up to %(count)s nights.', 'Choose an arrival within the permitted booking period.', 'Choose beds from the rooms above.', 'Choose between 1 and 30 guests.', 'Choose your arrival date.', 'Confirmed', 'Confirmed reservation', 'Could not refresh availability. Your details are kept. Please try again.', 'Departure', 'Departure must be after arrival.', 'Guests must be between 1 and %(count)s for this room.', 'No dates', 'Not enough beds on %(date)s. Choose an alternative below or adjust your stay.', 'Pending', 'Pending request', 'Preview %(guest)s reservation', 'Request reservation →', 'Saving reservation…', 'Select arrival and departure', 'Select beds to continue', 'Sending request…', 'Some nights are outside this calendar. Full availability is checked when you confirm.', 'Some quantities exceed availability. Adjust the room selections.', 'Some quantities were reduced to match availability.', 'Stay selection reset. Your guest details are kept.', 'This room is inactive. Choose another room.', 'You selected %(selected)s beds for %(target)s guests. Adjust beds or update your group size.', 'Your previous selection is kept.', 'bed', 'beds', 'guest', 'guests', 'night', 'nights', 'select dates')

def browser_messages():
    from .whole_units_v183 import whole_units
    aliases = {
      'bed': 'guest', 'beds': 'guests',
      'Choose beds to see the total': 'Choose a room to see the total',
      'Choose beds from the rooms above.': 'Choose accommodation above and enter the guests in each unit.',
      '%(selected)s of %(target)s beds': '%(selected)s of %(target)s guests',
      '%(selected)s of %(target)s beds selected. Choose %(remaining)s more.': '%(selected)s of %(target)s guests assigned. Assign %(remaining)s more.',
      'All %(target)s beds selected. Review your details and send the request.': 'All %(target)s guests assigned. Each selected unit is reserved exclusively.',
      'You selected %(selected)s beds for %(target)s guests. Adjust beds or update your group size.': 'You assigned %(selected)s guests for a group of %(target)s. Adjust guests or group size.',
      'Availability updated. Review your beds.': 'Availability updated. Review your accommodation.',
      'Not enough beds on %(date)s. Choose an alternative below or adjust your stay.': 'This unit is unavailable on %(date)s. Choose another unit or adjust your stay.',
      'Select beds to continue': 'Choose accommodation and assign guests to continue',
    } if whole_units() else {}
    result = {text: gettext(aliases.get(text, text)) for text in MESSAGES}
    result['Whole unit'] = gettext('Whole unit')
    return result
