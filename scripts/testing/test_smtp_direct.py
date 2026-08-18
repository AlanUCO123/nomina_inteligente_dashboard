import smtplib
from email.mime.text import MIMEText
import os

smtp_server = "mail.wyny.com.mx"
smtp_port = 25
smtp_user = "iracheta09"
smtp_password = "Wyny202520262027"
smtp_from = "iracheta09@wyny.com.mx"

print("=" * 70)
print("DIAGNÓSTICO SMTP".center(70))
print("=" * 70)
print(f"Servidor: {smtp_server}")
print(f"Puerto: {smtp_port}")
print(f"Usuario: {smtp_user}")
print(f"De: {smtp_from}")
print("-" * 70)

try:
    # Conectar al servidor
    print("\n[1/4] Conectando a servidor SMTP...")
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
    print("      ✓ Conexión exitosa")
    
    # Debug SMTP
    print("\n[2/4] Habilitando debug SMTP...")
    server.set_debuglevel(2)
    
    # Autenticar
    print("\n[3/4] Autenticando...")
    server.login(smtp_user, smtp_password)
    print("      ✓ Autenticación exitosa")
    
    # Crear y enviar mensaje
    print("\n[4/4] Enviando mensaje de prueba...")
    msg = MIMEText("Este es un mensaje de prueba de SMTP", "plain", "utf-8")
    msg["Subject"] = "PRUEBA SMTP - DIAGNÓSTICO"
    msg["From"] = smtp_from
    msg["To"] = "cesar_iracheta@wyny.com.mx"
    msg["Cc"] = "veronica_aranda@wyny.com.mx"
    
    destinatarios = ["cesar_iracheta@wyny.com.mx", "veronica_aranda@wyny.com.mx"]
    result = server.send_message(msg, to_addrs=destinatarios)
    print("      ✓ Mensaje enviado")
    print(f"      Resultado: {result}")
    
    server.quit()
    print("\n✓ DIAGNÓSTICO COMPLETADO SIN ERRORES")
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n✗ ERROR DE AUTENTICACIÓN: {e}")
except smtplib.SMTPException as e:
    print(f"\n✗ ERROR SMTP: {e}")
except Exception as e:
    print(f"\n✗ ERROR GENERAL: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
