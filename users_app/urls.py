from django.urls import path

from . import views

urlpatterns = [
    path('signup/assistant/', views.assistant_signup, name='assistant_signup'),
    path('signup/organizer/', views.organizer_signup, name='organizer_signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
]
