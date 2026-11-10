from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from allauth.account.forms import LoginForm
from .models import Interest


class TagsWidget(forms.HiddenInput):
    """Campo de etiquetas libres: el valor viaja como texto separado por comas."""
    template_name = 'users_app/widgets/tags.html'

    def __init__(self, attrs=None, placeholder=''):
        super().__init__(attrs)
        self.placeholder = placeholder

    def get_context(self, name, value, attrs):
        if isinstance(value, (list, tuple)):
            value = ', '.join(value)
        context = super().get_context(name, value, attrs)
        context['widget']['placeholder'] = self.placeholder
        return context


class TagsField(forms.Field):
    """Lista de etiquetas sin vacías ni duplicadas (sin distinguir mayúsculas), con espacios recortados."""
    widget = TagsWidget
    max_tag_length = 100

    def to_python(self, value):
        parts = value if isinstance(value, (list, tuple)) else (value or '').split(',')
        tags, seen = [], set()
        for part in parts:
            tag = ' '.join(str(part).split())
            if tag and tag.casefold() not in seen:
                seen.add(tag.casefold())
                tags.append(tag)
        return tags

    def validate(self, value):
        super().validate(value)
        if any(len(tag) > self.max_tag_length for tag in value):
            raise forms.ValidationError(f'Cada etiqueta admite hasta {self.max_tag_length} caracteres.')


def set_user_interests(user, names):
    """Reemplaza los intereses del usuario, reutilizando los existentes sin distinguir mayúsculas."""
    interests = [
        Interest.objects.filter(name__iexact=name).first() or Interest.objects.create(name=name)
        for name in names
    ]
    user.interests.set(interests)


FORM_INPUT_CLASSES = (
    'w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 '
    'text-sm text-white placeholder-slate-500 focus:border-indigo-500 '
    'focus:ring-1 focus:ring-indigo-500 focus:outline-none transition'
)


def _style_form_fields(form):
    for name, field in form.fields.items():
        if isinstance(field.widget, (forms.CheckboxSelectMultiple, TagsWidget)):
            continue
        if isinstance(field.widget, (forms.FileInput, forms.ClearableFileInput)):
            field.widget.attrs['class'] = (
                'block w-full text-sm text-slate-300 file:mr-4 file:py-2.5 file:px-4 '
                'file:rounded-xl file:border-0 file:text-sm file:font-semibold '
                'file:bg-indigo-600/30 file:text-indigo-300 hover:file:bg-indigo-600/50 cursor-pointer'
            )
            continue
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs['class'] = (
                'h-4 w-4 rounded border-slate-700 bg-slate-950 text-indigo-600 accent-indigo-600 focus:ring-indigo-500 cursor-pointer'
            )
            continue
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f"{existing} {FORM_INPUT_CLASSES}".strip()
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.setdefault('rows', 3)


class SiteLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        if 'login' in self.fields:
            self.fields['login'].label = 'Usuario o correo electrónico'
            self.fields['login'].widget.attrs.update({
                'placeholder': 'ejemplo@correo.com o tu usuario',
                'autocomplete': 'username',
            })
        if 'password' in self.fields:
            self.fields['password'].label = 'Contraseña'
            self.fields['password'].widget.attrs.update({
                'placeholder': 'Tu contraseña',
                'autocomplete': 'current-password',
            })
        if 'remember' in self.fields:
            self.fields['remember'].label = 'Recordarme'


def _normalize_signup_data(data):
    """
    Normaliza diccionarios POST de registro para soportar tanto password1/password2
    como un único campo 'password', además de alias de organización.
    """
    if not data:
        return data
    mutable = data.copy() if hasattr(data, 'copy') else dict(data)
    if 'password' in mutable and 'password1' not in mutable:
        mutable['password1'] = mutable['password']
        if 'password2' not in mutable:
            mutable['password2'] = mutable['password']
    elif 'password1' in mutable and 'password2' not in mutable and 'password' in mutable:
        mutable['password2'] = mutable['password1']
    if 'organization_name' in mutable and 'username' not in mutable:
        mutable['username'] = mutable['organization_name']
    if 'description' in mutable and 'organization_description' not in mutable:
        mutable['organization_description'] = mutable['description']
    if 'event_type' in mutable and 'organization_event_type' not in mutable:
        mutable['organization_event_type'] = mutable['event_type']
    return mutable


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

    def __init__(self, *args, **kwargs):
        if 'data' in kwargs and kwargs['data'] is not None:
            kwargs['data'] = _normalize_signup_data(kwargs['data'])
        elif len(args) > 0 and args[0] is not None:
            args = (_normalize_signup_data(args[0]),) + args[1:]
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        if 'username' in self.fields:
            self.fields['username'].widget.attrs.setdefault('placeholder', 'Nombre de usuario')
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.setdefault('placeholder', 'ejemplo@correo.com')
        if 'first_name' in self.fields:
            self.fields['first_name'].widget.attrs.setdefault('placeholder', 'Tu nombre')
        if 'last_name' in self.fields:
            self.fields['last_name'].widget.attrs.setdefault('placeholder', 'Tus apellidos')
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.setdefault('placeholder', 'Mínimo 8 caracteres (mayúscula, minúscula, número)')
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.setdefault('placeholder', 'Repite tu contraseña')

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
    interests = TagsField(
        label='Intereses',
        required=False,
        widget=TagsWidget(placeholder='Ej. Inteligencia artificial, Jazz en vivo...'),
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = get_user_model().Roles.ASSISTANT
        if commit:
            user.save()
            set_user_interests(user, self.cleaned_data['interests'])
        return user


class OrganizerSignupForm(BaseSignupForm):
    organization_event_type = TagsField(
        label='Especialidades',
        required=False,
        widget=TagsWidget(placeholder='Ej. Conferencias de tecnología, Ferias gastronómicas...'),
    )
    organization_description = forms.CharField(
        label='Descripción de la organización', widget=forms.Textarea, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Para organizaciones, el campo de nombre de usuario es el nombre de la organización
        self.fields['username'].label = 'Nombre de la organización'
        self.fields['username'].help_text = 'Este nombre identificará a tu organización y servirá para iniciar sesión.'
        self.fields['username'].widget.attrs['placeholder'] = 'Nombre de la organización'
        if 'organization_description' in self.fields:
            self.fields['organization_description'].widget.attrs['placeholder'] = 'Describe brevemente las actividades que realiza la organización...'
        _style_form_fields(self)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con este nombre de organización.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = get_user_model().Roles.ORGANIZER
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    interests = TagsField(
        label='Intereses',
        required=False,
        widget=TagsWidget(placeholder='Ej. Inteligencia artificial, Jazz en vivo...'),
    )

    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'location')
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'username': 'Nombre de usuario',
            'location': 'Ubicación',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user or self.instance
        if self.user and getattr(self.user, 'role', None) == get_user_model().Roles.ORGANIZER:
            self.fields['username'].label = 'Nombre de la organización'
            del self.fields['interests']  # los organizadores usan «Especialidades» en su organización
        elif self.instance.pk:
            self.initial['interests'] = list(self.instance.interests.values_list('name', flat=True))
        _style_form_fields(self)
        if 'first_name' in self.fields:
            self.fields['first_name'].widget.attrs.setdefault('placeholder', 'Tu nombre')
        if 'last_name' in self.fields:
            self.fields['last_name'].widget.attrs.setdefault('placeholder', 'Tus apellidos')
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.setdefault('placeholder', 'ejemplo@correo.com')
        if 'location' in self.fields:
            self.fields['location'].widget.attrs.setdefault('placeholder', 'Ej. Ciudad de México, Mérida...')

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
            if self.user and getattr(self.user, 'role', None) == get_user_model().Roles.ORGANIZER:
                raise forms.ValidationError('Ya existe una cuenta con este nombre de organización.')
            raise forms.ValidationError('Ya existe una cuenta con este nombre de usuario.')
        return username

    def save(self, commit=True):
        user = super().save(commit)
        if commit and 'interests' in self.fields:
            set_user_interests(user, self.cleaned_data['interests'])
        return user


class OrganizationProfileForm(forms.ModelForm):
    name = forms.CharField(label='Nombre de la organización', min_length=1, max_length=200, required=False)
    event_type = TagsField(
        label='Especialidades',
        required=False,
        widget=TagsWidget(placeholder='Ej. Conferencias de tecnología, Ferias gastronómicas...'),
    )

    class Meta:
        model = get_user_model().organization.field.related_model
        fields = ('name', 'description', 'event_type', 'logo')
        labels = {
            'name': 'Nombre de la organización',
            'description': 'Descripción',
            'logo': 'Logo institucional',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        if 'name' in self.fields:
            self.fields['name'].widget.attrs.setdefault('placeholder', 'Nombre de la organización')
        if 'description' in self.fields:
            self.fields['description'].widget.attrs.setdefault('placeholder', 'Descripción de la organización...')

    def clean_event_type(self):
        return ', '.join(self.cleaned_data['event_type'])
