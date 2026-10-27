from django.urls import path
from . import views

app_name = 'social_app'

urlpatterns = [
    # La URL recibirá el ID de la organización o evento como número entero (<int:...>)
    path('seguir/<int:organizacion_id>/', views.toggle_seguimiento, name='toggle_seguimiento'),
    path('favorito/<int:evento_id>/', views.toggle_favorito, name='toggle_favorito'),
]