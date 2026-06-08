"""
Módulo de envío de correos electrónicos vía Brevo SMTP.

Funciones:
  - send_reset_email: Correo de recuperación de contraseña.
  - send_tenant_welcome_email: Credenciales temporales para nuevos tenants (CU-29).

IMPORTANTE:
  - FROM_EMAIL debe ser un remitente verificado en Brevo (tu cuenta registrada).
  - Las URLs del frontend se construyen dinámicamente según el entorno.
"""

import smtplib
import logging
from email.message import EmailMessage
from app.shared.config import settings

logger = logging.getLogger(__name__)


def _get_frontend_base_url() -> str:
    """
    Determina la URL base del frontend según el entorno.
    En desarrollo (DEBUG_RESET_TOKEN=true) usa localhost.
    En producción usa la URL de Render/Vercel.
    """
    if settings.DEBUG_RESET_TOKEN:
        return "http://localhost:4200"
    # Intentar leer de variable de entorno, fallback a Vercel
    import os
    return os.getenv("FRONTEND_URL", "https://rutaigeoproxi.vercel.app")


def _send_email(msg: EmailMessage, context: str = "correo") -> None:
    """
    Envía un EmailMessage vía Brevo SMTP con logging profesional.
    Propaga excepciones para que BackgroundTasks las registre.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP no configurado (SMTP_USER o SMTP_PASSWORD vacíos). "
            "No se enviará %s.", context
        )
        return

    logger.info(
        "Enviando %s | FROM=%s | TO=%s | SMTP=%s:%s",
        context,
        settings.FROM_EMAIL,
        msg['To'],
        settings.SMTP_SERVER,
        settings.SMTP_PORT,
    )

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("✅ %s enviado exitosamente a %s", context, msg['To'])
    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            "❌ Error de autenticación SMTP. Verifica SMTP_USER y SMTP_PASSWORD. "
            "Detalle: %s", e
        )
        raise
    except smtplib.SMTPSenderRefused as e:
        logger.error(
            "❌ Remitente rechazado: FROM_EMAIL='%s' no está verificado en Brevo. "
            "Debes usar el email con el que registraste tu cuenta Brevo. "
            "Detalle: %s", settings.FROM_EMAIL, e
        )
        raise
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(
            "❌ Destinatario rechazado: TO='%s'. Detalle: %s", msg['To'], e
        )
        raise
    except smtplib.SMTPException as e:
        logger.error("❌ Error SMTP al enviar %s: %s", context, e)
        raise
    except Exception as e:
        logger.error("❌ Error inesperado al enviar %s: %s", context, e)
        raise


def send_reset_email(to_email: str, token: str):
    """
    Envía el correo de recuperación de contraseña vía Brevo (SMTP).
    """
    frontend_url = _get_frontend_base_url()
    reset_url = f"{frontend_url}/reset-password?token={token}"

    msg = EmailMessage()
    msg['Subject'] = "Recuperación de Contraseña - RutAIGeoProxi"
    msg['From'] = settings.FROM_EMAIL
    msg['To'] = to_email

    html_content = f"""
    <!DOCTYPE html>
    <html>
      <body style="margin: 0; padding: 0; background-color: #121212; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #121212; padding: 40px 0;">
          <tr>
            <td align="center">
              <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #1E1E1E; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                <!-- Header -->
                <tr>
                  <td style="background-color: #2A2A2A; padding: 20px; text-align: center; border-bottom: 2px solid #00F2FF;">
                    <h1 style="color: #00F2FF; margin: 0; font-size: 24px; letter-spacing: 2px;">RUT<span style="color: #FFF;">AI</span>GEOPROXI</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding: 40px 30px;">
                    <h2 style="color: #FFFFFF; font-size: 20px; margin-top: 0;">¡Hola!</h2>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-bottom: 30px;">
                      Estás recibiendo este correo porque recibimos una solicitud de recuperación de contraseña para tu cuenta.
                    </p>
                    
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center">
                          <a href="{reset_url}" style="display: inline-block; background-color: #00F2FF; color: #000000; font-weight: bold; font-size: 16px; text-decoration: none; padding: 14px 30px; border-radius: 4px;">
                            Restablecer Contraseña
                          </a>
                        </td>
                      </tr>
                    </table>

                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-top: 30px;">
                      Este enlace de recuperación expirará en 60 minutos.
                    </p>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5;">
                      Si no solicitaste un cambio de contraseña, no es necesario realizar ninguna acción.
                    </p>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-top: 30px;">
                      Saludos,<br>
                      <strong style="color: #FFFFFF;">El equipo de RutAIGeoProxi</strong>
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #333333; margin: 30px 0;">
                    
                    <p style="color: #777777; font-size: 13px; line-height: 1.5; word-break: break-all;">
                      Si tienes problemas para hacer clic en el botón "Restablecer Contraseña", copia y pega la siguiente URL en tu navegador web:<br>
                      <a href="{reset_url}" style="color: #0096FF; text-decoration: none;">{reset_url}</a>
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="background-color: #1A1A1A; padding: 20px; text-align: center;">
                    <p style="color: #777777; font-size: 12px; margin: 0;">
                      © 2026 RutAIGeoProxi. Todos los derechos reservados.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    msg.set_content(html_content, subtype='html')
    _send_email(msg, context="correo de recuperación de contraseña")


def send_tenant_welcome_email(to_email: str, tenant_name: str, temp_password: str):
    """
    Envía el correo de bienvenida al nuevo administrador del tenant (CU-29).
    Incluye las credenciales temporales generadas automáticamente.
    """
    frontend_url = _get_frontend_base_url()
    login_url = f"{frontend_url}/login"

    msg = EmailMessage()
    msg['Subject'] = f"¡Bienvenido a RutAIGeoProxi! Accesos para {tenant_name}"
    msg['From'] = settings.FROM_EMAIL
    msg['To'] = to_email

    html_content = f"""
    <!DOCTYPE html>
    <html>
      <body style="margin: 0; padding: 0; background-color: #121212; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #E0E0E0;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #121212; padding: 40px 0;">
          <tr>
            <td align="center">
              <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #1E1E1E; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                <!-- Header -->
                <tr>
                  <td style="background-color: #2A2A2A; padding: 20px; text-align: center; border-bottom: 2px solid #00F2FF;">
                    <h1 style="color: #00F2FF; margin: 0; font-size: 24px; letter-spacing: 2px;">RUT<span style="color: #FFF;">AI</span>GEOPROXI</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding: 40px 30px;">
                    <h2 style="color: #FFFFFF; font-size: 20px; margin-top: 0;">¡Hola!</h2>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-bottom: 20px;">
                      Tu organización <strong>{tenant_name}</strong> ha sido creada exitosamente en nuestra plataforma SaaS.
                    </p>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-bottom: 30px;">
                      A continuación, te proporcionamos tus credenciales de acceso temporal como Administrador:
                    </p>
                    
                    <div style="background-color: #2A2A2A; padding: 15px; border-radius: 4px; border-left: 4px solid #00F2FF; margin-bottom: 30px;">
                      <p style="margin: 0; font-family: monospace; font-size: 16px;">
                        <strong>Usuario:</strong> {to_email}<br>
                        <strong>Contraseña Temporal:</strong> {temp_password}
                      </p>
                    </div>

                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center">
                          <a href="{login_url}" style="display: inline-block; background-color: #00F2FF; color: #000000; font-weight: bold; font-size: 16px; text-decoration: none; padding: 14px 30px; border-radius: 4px;">
                            Iniciar Sesión
                          </a>
                        </td>
                      </tr>
                    </table>

                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-top: 30px;">
                      Te recomendamos cambiar esta contraseña temporal una vez ingreses a la plataforma, en la sección de tu perfil.
                    </p>
                    <p style="color: #B0B0B0; font-size: 16px; line-height: 1.5; margin-top: 30px;">
                      Saludos,<br>
                      <strong style="color: #FFFFFF;">El equipo de RutAIGeoProxi</strong>
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="background-color: #1A1A1A; padding: 20px; text-align: center;">
                    <p style="color: #777777; font-size: 12px; margin: 0;">
                      © 2026 RutAIGeoProxi. Todos los derechos reservados.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    msg.set_content(html_content, subtype='html')
    _send_email(msg, context=f"correo de bienvenida tenant '{tenant_name}'")
