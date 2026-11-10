from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from social_app.views import my_favorites
from users_app.views import confirm_email, home, login, signup_disabled

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', login, name='account_login'),
    path('accounts/signup/', signup_disabled, name='account_signup'),
    path('accounts/confirm-email/<str:key>/', confirm_email, name='account_confirm_email'),
    path('accounts/', include('allauth.urls')),
    path('users/', include('users_app.urls')),
    path('events/', include('events_app.urls')),
    path('my-registrations/', include('registrations_app.urls')),
    path('registrations/', include('registrations_app.urls')),
    path('social/', include('social_app.urls')),
    path('my-favorites/', my_favorites, name='my_favorites_root'),
    path('discovery/', include('discovery_app.urls')),
    path('', home, name='home'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
