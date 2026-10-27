from django.urls import path
from . import views

urlpatterns = [
    path('', views.discovery_view, name='discovery'),
    path('api/recommendations/', views.recommendations_api, name='discovery_api_recommendations'),
]
