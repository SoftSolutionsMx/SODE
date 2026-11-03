from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_registrations, name='my_registrations'),
    path('<int:inscripcion_id>/cancel/', views.cancel_registration, name='cancel_registration'),
    path('event/<int:event_id>/cancel/', views.cancel_registration_by_event, name='cancel_registration_by_event'),
    path('<int:inscripcion_id>/ticket/', views.attendance_ticket, name='attendance_ticket'),
    path('event/<int:event_id>/register/', views.register_to_event, name='register_to_event_alt'),
]
