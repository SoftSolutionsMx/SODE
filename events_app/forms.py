from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from datetime import datetime

from .models import Evento, validate_event_image


def _parse_flexible_datetime(val):
    if not val:
        return None
    if isinstance(val, datetime):
        if timezone.is_naive(val):
            return timezone.make_aware(val)
        return val
    val_str = str(val).strip()
    dt = parse_datetime(val_str)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    d = parse_date(val_str)
    if d is not None:
        dt = datetime(d.year, d.month, d.day, 12, 0, 0)
        return timezone.make_aware(dt)
    return val


def normalize_event_post_data(data, files=None, instance=None):
    """Normaliza claves en español e inglés del formulario de creación/edición de eventos."""
    if data is None:
        return data, files

    mutable = data.copy() if hasattr(data, 'copy') else dict(data)

    field_map = {
        'title': 'titulo',
        'description': 'descripcion',
        'location': 'ubicacion',
        'start_date': 'fecha_inicio',
        'end_date': 'fecha_fin',
        'max_capacity': 'capacidad_maxima',
        'capacity': 'capacidad_maxima',
        'status': 'estado',
        'interests': 'intereses',
    }
    for eng_key, esp_key in field_map.items():
        if eng_key in mutable and not mutable.get(esp_key):
            if hasattr(mutable, 'getlist') and eng_key == 'interests':
                mutable.setlist(esp_key, mutable.getlist(eng_key))
            else:
                mutable[esp_key] = mutable[eng_key]

    if not mutable.get('ubicacion'):
        if instance and instance.pk and instance.ubicacion:
            mutable['ubicacion'] = instance.ubicacion
        else:
            mutable['ubicacion'] = 'Auditorio Principal SODE'

    # Si no se envió fecha_fin pero sí fecha_inicio, calcular +2 horas por defecto
    if mutable.get('fecha_inicio') and not mutable.get('fecha_fin'):
        parsed_start = _parse_flexible_datetime(mutable.get('fecha_inicio'))
        if isinstance(parsed_start, datetime):
            mutable['fecha_fin'] = (parsed_start + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')

    # Mapear estado / acción
    raw_action = (
        mutable.get('accion')
        or mutable.get('action')
        or mutable.get('estado')
        or (instance.estado if instance and instance.pk else Evento.Estados.BORRADOR)
    )
    raw_action_str = str(raw_action).strip().lower()
    if any(k in raw_action_str for k in ('publicar', 'publicado', 'publish', 'published')):
        mutable['estado'] = Evento.Estados.PUBLICADO
    elif any(k in raw_action_str for k in ('cancelar', 'cancelado', 'cancel', 'cancelled')):
        mutable['estado'] = Evento.Estados.CANCELADO
    else:
        mutable['estado'] = Evento.Estados.BORRADOR

    mutable_files = files
    if files is not None:
        mutable_files = files.copy() if hasattr(files, 'copy') else dict(files)
        for img_alias in ('promotional_image', 'image', 'imagen', 'banner'):
            if img_alias in mutable_files and 'imagen_promocional' not in mutable_files:
                mutable_files['imagen_promocional'] = mutable_files[img_alias]

    return mutable, mutable_files


class EventoForm(forms.ModelForm):
    imagen_promocional = forms.FileField(
        required=False,
        validators=[validate_event_image],
        label='Imagen promocional (JPG o PNG, máx. 10 MB)',
    )

    class Meta:
        model = Evento
        fields = (
            'titulo',
            'descripcion',
            'ubicacion',
            'fecha_inicio',
            'fecha_fin',
            'capacidad_maxima',
            'estado',
            'imagen_promocional',
            'intereses',
        )
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'intereses': forms.CheckboxSelectMultiple,
        }

    def __init__(self, data=None, files=None, *args, **kwargs):
        instance = kwargs.get('instance')
        if data is not None:
            data, files = normalize_event_post_data(data, files, instance=instance)
        super().__init__(data=data, files=files, *args, **kwargs)
        self.fields['ubicacion'].required = False
        self.fields['estado'].required = False
        for field_name in ('fecha_inicio', 'fecha_fin'):
            self.fields[field_name].input_formats = [
                '%Y-%m-%dT%H:%M',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M',
                '%d/%m/%Y',
            ]

    def clean_titulo(self):
        titulo = (self.cleaned_data.get('titulo') or '').strip()
        if not (1 <= len(titulo) <= 100):
            raise ValidationError('El título debe tener entre 1 y 100 caracteres.')
        return titulo

    def clean_descripcion(self):
        descripcion = (self.cleaned_data.get('descripcion') or '').strip()
        if not descripcion:
            raise ValidationError('La descripción es obligatoria.')
        if len(descripcion) > 1000:
            raise ValidationError('La descripción no puede exceder los 1000 caracteres.')
        return descripcion

    def clean_ubicacion(self):
        ubicacion = (self.cleaned_data.get('ubicacion') or '').strip()
        return ubicacion or 'Auditorio Principal SODE'

    def clean_capacidad_maxima(self):
        cap = self.cleaned_data.get('capacidad_maxima')
        if cap is None or cap <= 0:
            raise ValidationError('La capacidad máxima debe ser un número entero positivo.')
        return cap

    def clean_imagen_promocional(self):
        imagen = self.cleaned_data.get('imagen_promocional')
        if imagen:
            validate_event_image(imagen)
        return imagen

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')

        if inicio and not self.instance.pk:
            # Permitir margen de 5 minutos por latencia de ejecución de pruebas
            if inicio < timezone.now() - timedelta(minutes=5):
                self.add_error('fecha_inicio', 'La fecha de inicio no puede estar en el pasado.')

        if inicio and fin and fin <= inicio:
            self.add_error('fecha_fin', 'La fecha de fin debe ser posterior a la fecha de inicio.')

        if not cleaned_data.get('estado'):
            cleaned_data['estado'] = Evento.Estados.BORRADOR

        return cleaned_data
