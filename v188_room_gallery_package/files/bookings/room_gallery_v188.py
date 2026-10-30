"""Room-scoped gallery forms; the parent room owns all uploaded photos."""
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import Room, RoomPhoto

class ScopedPhotoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            photo = form.cleaned_data.get('id') if hasattr(form, 'cleaned_data') else None
            if photo and photo.room_id != self.instance.pk:
                raise ValidationError('A gallery photo belongs to another room.')

RoomPhotoFormSet = inlineformset_factory(
    Room, RoomPhoto, formset=ScopedPhotoFormSet,
    fields=('image','caption','position'), extra=1, can_delete=True,
)
