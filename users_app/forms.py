from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password


class BaseSignupForm(forms.ModelForm):
    username = forms.CharField(label='Nombre de usuario', min_length=1, max_length=200)
    password1 = forms.CharField(
        label='Contraseña',
        min_length=8,
        max_length=50,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con este nombre de usuario.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password1')
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
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
    organization_name = forms.CharField(label='Nombre de la organización', min_length=1, max_length=200)
    organization_event_type = forms.CharField(
        label='Tipología de eventos', min_length=1, max_length=200
    )
    organization_description = forms.CharField(
        label='Descripción de la organización', widget=forms.Textarea, required=False
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = get_user_model().Roles.ORGANIZER
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'location', 'interests')
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'username': 'Nombre de usuario',
            'location': 'Ubicación',
            'interests': 'Intereses',
        }
        widgets = {
            'interests': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user or self.instance

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if get_user_model().objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(
            username__iexact=username
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe una cuenta con este nombre de usuario.')
        return username


class OrganizationProfileForm(forms.ModelForm):
    name = forms.CharField(label='Nombre de la organización', min_length=1, max_length=200)

    class Meta:
        model = get_user_model().organization.field.related_model
        fields = ('name', 'description', 'event_type')
        labels = {
            'name': 'Nombre de la organización',
            'description': 'Descripción',
            'event_type': 'Tipología de eventos',
        }
