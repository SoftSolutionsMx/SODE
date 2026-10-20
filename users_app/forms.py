from django import forms
from django.contrib.auth import get_user_model


class BaseSignupForm(forms.ModelForm):
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ('email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AssistantSignupForm(BaseSignupForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = get_user_model().Roles.ASSISTANT
        if commit:
            user.save()
        return user


class OrganizerSignupForm(BaseSignupForm):
    organization_name = forms.CharField(label='Nombre de la organización', max_length=150)
    organization_description = forms.CharField(
        label='Descripción de la organización', widget=forms.Textarea, required=False
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = get_user_model().Roles.ORGANIZER
        if commit:
            user.save()
        return user
