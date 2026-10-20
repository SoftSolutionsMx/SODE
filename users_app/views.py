from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseNotFound
from django.shortcuts import redirect, render
from allauth.account.views import LoginView
from allauth.account.models import EmailAddress

from .forms import AssistantSignupForm, OrganizerSignupForm
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
            EmailAddress.objects.create(
                user=user, email=user.email, primary=True, verified=True
            )
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
            )
            EmailAddress.objects.create(
                user=user, email=user.email, primary=True, verified=True
            )
            return redirect('signup_success')
    return render(request, 'users_app/signup.html', {'form': form, 'title': 'Crear cuenta de organizador'})


def signup_success(request):
    return render(request, 'users_app/signup_success.html')
