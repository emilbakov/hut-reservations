from django.urls import path
from . import views
app_name = "floorplans"
urlpatterns = [
    path("<int:hut_id>/edit/", views.editor, name="editor"),
    path("<int:hut_id>/data/", views.data, name="data"),
    path("<int:hut_id>/save/", views.save, name="save"),
    path("<int:hut_id>/availability/", views.availability, name="availability"),
]
