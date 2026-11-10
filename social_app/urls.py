from django.urls import path
from . import views

urlpatterns = [
    path('favorites/', views.my_favorites, name='my_favorites'),
    path('follow/<int:org_id>/', views.toggle_follow_organization, name='toggle_follow_organization'),
    path('favorite/<int:event_id>/', views.toggle_favorite_event, name='toggle_favorite_event'),
]
