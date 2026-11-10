import logging
from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)


class EmailServiceAccountAdapter(DefaultAccountAdapter):
    """
    Adaptador de cuenta personalizado para django-allauth que enruta
    el envío de correos del sistema de autenticación a través del servicio de correo.
    """

    def send_mail(self, template_prefix, email, context):
        logger.info(f"Enviando correo allauth con plantilla '{template_prefix}' a '{email}'.")
        msg = self.render_mail(template_prefix, email, context)
        if 'email_confirmation' in str(template_prefix):
            msg.subject = 'Activa tu cuenta en SODE'
        return msg.send()
