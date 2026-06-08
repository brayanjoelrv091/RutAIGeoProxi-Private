import smtplib
from email.message import EmailMessage

SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587
SMTP_USER = "a8732b001@smtp-brevo.com"
SMTP_PASSWORD = "xsmtpsib-1613a92b56bbf3291c9abb38d9738cd0ac2d8c8e3aabbab965f0d9617c23756e-jr1DXpWPqKGlm56m"
FROM_EMAIL = "brayanjoelrv091@gmail.com" # Assuming this is his email
TO_EMAIL = "brayanjoelrv091@gmail.com"

msg = EmailMessage()
msg['Subject'] = "Prueba de Brevo SMTP"
msg['From'] = FROM_EMAIL
msg['To'] = TO_EMAIL
msg.set_content("Este es un correo de prueba desde Python.")

try:
    print("Conectando al servidor SMTP...")
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.set_debuglevel(1)
        server.starttls()
        print("Autenticando...")
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("Enviando mensaje...")
        server.send_message(msg)
    print("¡Correo enviado con éxito!")
except Exception as e:
    print(f"ERROR: {e}")
