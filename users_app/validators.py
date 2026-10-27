from django.core.exceptions import ValidationError


class PasswordRequirementsValidator:
    def validate(self, password, user=None):
        if not any(character.isupper() for character in password):
            raise ValidationError(
                'La contraseña debe contener al menos una letra mayúscula.'
            )
        if not any(character.isdigit() for character in password):
            raise ValidationError(
                'La contraseña debe contener al menos un número.'
            )

    def get_help_text(self):
        return 'La contraseña debe contener al menos una letra mayúscula y un número.'
