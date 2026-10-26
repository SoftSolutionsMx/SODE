from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseNotFound
from django.shortcuts import redirect, render
from allauth.account.views import LoginView
from allauth.account.models import EmailAddress

from .forms import (
    AssistantSignupForm,
    OrganizationProfileForm,
    OrganizerSignupForm,
    ProfileForm,
)
from .models import Organization


def home(request):
    return render(request, 'users_app/home.html')


class SiteLoginView(LoginView):
    template_name = 'account/login.html'

    def form_valid(self, form):
        messages.success(self.request, f'Sesión iniciada correctamente como {form.user.email}.')
        return super().form_valid(form)


login = SiteLoginView.as_view()


def signup_disabled(request):
    return HttpResponseNotFound('El registro general no está disponible.')


def assistant_signup(request):
    with transaction.atomic():
        form = AssistantSignupForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            user = form.save()
            _configure_email_verification(request, user)
            return redirect('signup_success')
    return render(request, 'users_app/signup.html', {'form': form, 'title': 'Crear cuenta de asistente'})


def organizer_signup(request):
    with transaction.atomic():
        form = OrganizerSignupForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            user = form.save()
            Organization.objects.create(
                user=user,
                name=form.cleaned_data['organization_name'],
                description=form.cleaned_data['organization_description'],
                event_type=form.cleaned_data['organization_event_type'],
            )
            _configure_email_verification(request, user)
            return redirect('signup_success')
    return render(request, 'users_app/signup.html', {'form': form, 'title': 'Crear cuenta de organizador'})


def signup_success(request):
    return render(request, 'users_app/signup_success.html', {
        'email_verification_enabled': settings.SODE_EMAIL_VERIFICATION,
    })


def _configure_email_verification(request, user):
    verified = not settings.SODE_EMAIL_VERIFICATION
    email_address = EmailAddress.objects.create(
        user=user, email=user.email, primary=True, verified=verified
    )
    if not verified:
        email_address.send_confirmation(request, signup=True)
    return email_address


@login_required
def profile(request):
    organization = getattr(request.user, 'organization', None)
    if request.method == 'POST':
        previous_email = request.user.email
        user_form = ProfileForm(request.POST, instance=request.user, user=request.user)
        organization_form = (
            OrganizationProfileForm(request.POST, instance=organization)
            if request.user.role == request.user.Roles.ORGANIZER and organization
            else None
        )
        if user_form.is_valid() and (organization_form is None or organization_form.is_valid()):
            user = user_form.save()
            if previous_email.lower() != user.email.lower():
                EmailAddress.objects.filter(user=user).delete()
                _configure_email_verification(request, user)
            elif not EmailAddress.objects.filter(user=user, email__iexact=user.email).exists():
                _configure_email_verification(request, user)
            if organization_form:
                organization_form.save()
            messages.success(request, 'Tu perfil se actualizó correctamente.')
            return redirect('profile')
    else:
        user_form = ProfileForm(instance=request.user, user=request.user)
        organization_form = (
            OrganizationProfileForm(instance=organization)
            if request.user.role == request.user.Roles.ORGANIZER and organization
            else None
        )
    return render(request, 'users_app/profile.html', {
        'user_form': user_form,
        'organization_form': organization_form,
    })
