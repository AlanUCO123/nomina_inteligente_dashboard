import smtplib
from email.mime.text import MIMEText

smtp_server = "mail.wyny.com.mx"
smtp_port = 25
smtp_user = "iracheta09"
smtp_password = "Wyny202520262027"
smtp_from = "iracheta09@wyny.com.mx"

# Enviar a tu email personal (fuera del servidor corporativo)
destinatarios = ["cesar.iracheta@gmail.com"]  # Cambia a tu email real si es diferente

msg = MIMEText("""
Hola Cesar,

Este es un email de prueba directo desde el sistema NOVA.

Si recibes este mensaje, el SMTP está funcionando correctamente.

Sistema de Control de HE - NOVA Personal
""", "plain", "utf-8")

msg["Subject"] = "PRUEBA SMTP NOVA - Email Directo"
msg["From"] = smtp_from
msg["To"] = ", ".join(destinatarios)

try:
    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
        # Sin STARTTLS en puerto 25
        server.login(smtp_user, smtp_password)
        server.send_message(msg, to_addrs=destinatarios)
    
    print("✓ Email de prueba enviado a:", destinatarios[0])
    
except Exception as e:
    print(f"✗ Error: {e}")
