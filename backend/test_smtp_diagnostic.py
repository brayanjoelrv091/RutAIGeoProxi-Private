"""
Script de diagnostico SMTP para Brevo.
Prueba la conexion, autenticacion y envio paso a paso.
Ejecutar: python test_smtp_diagnostic.py
"""

import smtplib
import ssl
from email.message import EmailMessage

# -- Configuracion (misma que tienes en Render) --
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587
SMTP_USER = "a8732b001@smtp-brevo.com"
SMTP_PASSWORD = "xsmtpsib-1613a92b56bbf3291c9abb38d9738cd0ac2d8c8e3aabbab965f0d9617c23756e-jr1DXpWPqKGlm56m"

# ESTO ES LO CLAVE: Debe ser el email verificado en Brevo
FROM_EMAIL = "si2psicologiaproy@gmail.com"
TO_EMAIL = "brayanjoelrv091@gmail.com"


def run_diagnostic():
    print("=" * 60)
    print("[DIAG] DIAGNOSTICO SMTP - BREVO")
    print("=" * 60)
    
    # Paso 1: Verificar configuracion
    print(f"\n[CONFIG] Configuracion:")
    print(f"   SMTP_SERVER  = {SMTP_SERVER}")
    print(f"   SMTP_PORT    = {SMTP_PORT}")
    print(f"   SMTP_USER    = {SMTP_USER}")
    print(f"   SMTP_PASSWORD= {'*' * 10}...{SMTP_PASSWORD[-6:]}")
    print(f"   FROM_EMAIL   = {FROM_EMAIL}")
    print(f"   TO_EMAIL     = {TO_EMAIL}")

    # Paso 2: Resolver DNS
    print(f"\n[DNS] Paso 1: Resolviendo DNS de {SMTP_SERVER}...")
    try:
        import socket
        ip = socket.gethostbyname(SMTP_SERVER)
        print(f"   [OK] Resuelto a {ip}")
    except socket.gaierror as e:
        print(f"   [FAIL] Error DNS: {e}")
        print("   -> No se puede resolver el servidor SMTP.")
        return

    # Paso 3: Conectar
    print(f"\n[CONN] Paso 2: Conectando a {SMTP_SERVER}:{SMTP_PORT}...")
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.set_debuglevel(0)
        print(f"   [OK] Conexion establecida")
    except (smtplib.SMTPConnectError, ConnectionRefusedError, TimeoutError) as e:
        print(f"   [FAIL] Error de conexion: {e}")
        print("   -> Puerto 587 bloqueado por firewall?")
        return

    # Paso 4: STARTTLS
    print(f"\n[TLS] Paso 3: Iniciando TLS (STARTTLS)...")
    try:
        server.starttls()
        print(f"   [OK] TLS activado")
    except smtplib.SMTPException as e:
        print(f"   [FAIL] Error TLS: {e}")
        server.quit()
        return

    # Paso 5: Login
    print(f"\n[AUTH] Paso 4: Autenticando con SMTP_USER...")
    try:
        server.login(SMTP_USER, SMTP_PASSWORD)
        print(f"   [OK] Autenticacion exitosa")
    except smtplib.SMTPAuthenticationError as e:
        print(f"   [FAIL] Error de autenticacion: {e}")
        print("   -> Verifica SMTP_USER y SMTP_PASSWORD en Brevo.")
        print("   -> app.brevo.com -> Transactional -> SMTP & API -> SMTP")
        server.quit()
        return

    # Paso 6: Enviar
    print(f"\n[SEND] Paso 5: Enviando correo de prueba...")
    msg = EmailMessage()
    msg['Subject'] = "[OK] Diagnostico SMTP Exitoso - RutAIGeoProxi"
    msg['From'] = FROM_EMAIL
    msg['To'] = TO_EMAIL
    msg.set_content(f"""
    Este correo confirma que la configuracion SMTP de Brevo funciona correctamente.
    
    FROM: {FROM_EMAIL}
    TO: {TO_EMAIL}
    SMTP: {SMTP_SERVER}:{SMTP_PORT}
    """)

    try:
        refused = server.send_message(msg)
        if refused:
            print(f"   [WARN] Algunos destinatarios rechazados: {refused}")
        else:
            print(f"   [OK] Correo enviado exitosamente!")
            print(f"   -> Revisa la bandeja de entrada de {TO_EMAIL}")
            print(f"   -> Tambien revisa la carpeta de SPAM")
    except smtplib.SMTPSenderRefused as e:
        print(f"   [FAIL] REMITENTE RECHAZADO: {e}")
        print(f"   -> El FROM_EMAIL '{FROM_EMAIL}' NO esta verificado en Brevo.")
        print(f"   -> Solucion: app.brevo.com -> Settings -> Senders -> verifica este email.")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"   [FAIL] DESTINATARIO RECHAZADO: {e}")
    except smtplib.SMTPDataError as e:
        print(f"   [FAIL] ERROR DE DATOS SMTP: {e}")
        print(f"   -> Codigo {e.smtp_code}: {e.smtp_error}")
    except smtplib.SMTPException as e:
        print(f"   [FAIL] ERROR SMTP: {e}")

    server.quit()
    print("\n" + "=" * 60)
    print("[DONE] Diagnostico completado.")
    print("=" * 60)


if __name__ == "__main__":
    run_diagnostic()
