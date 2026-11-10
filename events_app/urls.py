from django.urls import path
from registrations_app import views as reg_views
from . import views

urlpatterns = [
    path('create/', views.create_event, name='create_event'),
    path('my-events/', views.my_events, name='my_events'),
    path('<int:event_id>/', views.event_detail, name='event_detail'),
    path('<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('<int:event_id>/publish/', views.publish_event, name='publish_event'),
    path('<int:event_id>/unpublish/', views.unpublish_event, name='unpublish_event'),
    path('<int:event_id>/cancel/', views.cancel_event, name='cancel_event'),
    path('<int:event_id>/register/', reg_views.register_to_event, name='register_to_event'),
    path('<int:event_id>/attendees/', reg_views.event_attendees, name='event_attendees'),
    path('<int:event_id>/attendees/<int:inscripcion_id>/admit/', reg_views.admit_attendee, name='admit_attendee'),
    path('<int:event_id>/attendees/<int:inscripcion_id>/reject/', reg_views.reject_attendee, name='reject_attendee'),
]
