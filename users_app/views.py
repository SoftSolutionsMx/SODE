from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from allauth.account.views import ConfirmEmailView, LoginView

from email_service.services import send_verification_email

from .forms import (
    AssistantSignupForm,
    OrganizationProfileForm,
    OrganizerSignupForm,
    ProfileForm,
    SiteLoginForm,
)
from .models import Organization


def home(request):
    featured_events = []
    try:
        from events_app.models import Evento
        featured_events = list(
            Evento.objects.filter(estado=Evento.Estados.PUBLICADO)
            .select_related('organizacion')
            .prefetch_related('intereses')[:6]
        )
    except Exception:
        featured_events = []
    return render(request, 'users_app/home.html', {
        'featured_events': featured_events,
    })


class SiteLoginView(LoginView):
    form_class = SiteLoginForm
    template_name = 'users_app/login.html'

    def form_valid(self, form):
        messages.success(self.request, f'Sesión iniciada correctamente como {form.user.username}.')
        return super().form_valid(form)


login = SiteLoginView.as_view()


class SodeConfirmEmailView(ConfirmEmailView):
    template_name = 'account/email_confirm.html'

    def get(self, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Http404:
            self.object = None

        if self.object is not None:
            email_address = self.object.email_address
            try:
                self.object.confirm(self.request)
            except Exception:
                pass
            if not email_address.verified:
                email_address.verified = True
                email_address.save(update_fields=['verified'])
            auth_login(
                self.request,
                email_address.user,
                backend='django.contrib.auth.backends.ModelBackend',
            )
            messages.success(self.request, 'Cuenta activada exitosamente')

        context = self.get_context_data()
        if self.object is not None:
            context['can_confirm'] = True
            context['activated'] = True
        return self.render_to_response(context)

    def post(self, *args, **kwargs):
        try:
            self.object = self.get_object()
        except Http404:
            self.object = None

        if self.object is not None:
            email_address = self.object.email_address
            try:
                self.object.confirm(self.request)
            except Exception:
                pass
            if not email_address.verified:
                email_address.verified = True
                email_address.save(update_fields=['verified'])
            auth_login(
                self.request,
                email_address.user,
                backend='django.contrib.auth.backends.ModelBackend',
            )
            messages.success(self.request, 'Cuenta activada exitosamente')
            return redirect('home')

        context = self.get_context_data()
        return self.render_to_response(context)


confirm_email = SodeConfirmEmailView.as_view()


def signup_disabled(request):
    return redirect('assistant_signup')


def assistant_signup(request):
    form = AssistantSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
        send_verification_email(request, user, signup=True)
        messages.info(
            request,
            'Se ha enviado un correo de verificación a tu bandeja de entrada. Revisa tu correo para activar tu cuenta.',
        )
        return redirect('signup_success')
    return render(request, 'users_app/signup.html', {'form': form, 'title': 'Crear cuenta de asistente'})


def organizer_signup(request):
    form = OrganizerSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Organization.objects.create(
                user=user,
                name=user.username,
                description=form.cleaned_data.get('organization_description', ''),
                event_type=form.cleaned_data.get('organization_event_type', '') or 'General',
            )
        send_verification_email(request, user, signup=True)
        messages.info(
            request,
            'Se ha enviado un correo de verificación a tu bandeja de entrada. Revisa tu correo para activar tu cuenta.',
        )
        return redirect('signup_success')
    return render(request, 'users_app/signup.html', {'form': form, 'title': 'Crear cuenta de organizador'})


def signup_success(request):
    return render(request, 'users_app/signup_success.html', {
        'email_verification_enabled': settings.SODE_EMAIL_VERIFICATION,
    })


@login_required
def profile(request):
    organization = getattr(request.user, 'organization', None)
    if request.method == 'POST':
        previous_email = request.user.email
        user_form = ProfileForm(request.POST, instance=request.user, user=request.user)
        organization_form = (
            OrganizationProfileForm(request.POST, request.FILES, instance=organization)
            if request.user.role == request.user.Roles.ORGANIZER and organization
            else None
        )
        if user_form.is_valid() and (organization_form is None or organization_form.is_valid()):
            with transaction.atomic():
                user = user_form.save()
                if organization_form:
                    organization = organization_form.save(commit=False)
                    org_name = organization_form.cleaned_data.get('name') or user.username
                    organization.name = org_name
                    organization.save()
                    if user.username != org_name:
                        user.username = org_name
                        user.save(update_fields=['username'])
            email_changed = previous_email.lower() != user.email.lower()
            send_verification_email(request, user, signup=False, replace_existing=email_changed)
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
