from django.db import models


class RecommendationParameter(models.Model):
    DEFAULT_WEIGHTS = {
        'weight_interests': 0.40,
        'weight_proximity': 0.30,
        'weight_social': 0.20,
        'weight_collaborative': 0.10,
    }

    name = models.CharField(
        max_length=60,
        unique=True,
        verbose_name='Nombre del parámetro',
    )
    value = models.FloatField(
        default=1.0,
        verbose_name='Valor / Peso',
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Descripción',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última actualización',
    )

    class Meta:
        verbose_name = 'Parámetro de recomendación'
        verbose_name_plural = 'Parámetros de recomendación'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}: {self.value}'

    @classmethod
    def get_weights(cls):
        """
        Devuelve un diccionario con los pesos activos del algoritmo de recomendación.
        Si no existen en BD, utiliza los valores por defecto establecidos.
        """
        weights = dict(cls.DEFAULT_WEIGHTS)
        try:
            stored_params = cls.objects.filter(name__in=weights.keys())
            for param in stored_params:
                weights[param.name] = float(param.value)
        except Exception:
            # Manejo de fallback si la tabla aún no ha sido migrada
            pass
        return weights
