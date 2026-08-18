# Configuración SMTP para NOVA Personal
# Este archivo documenta la configuración actual del servidor de email

[SMTP]
Servidor = mail.wyny.com.mx
Puerto = 587
Usuario = iracheta09
Contraseña = Wyny202520262027
De = iracheta09@wyny.com.mx
TLS = No

[Características]
- Puerto 587 sin TLS (basado en pruebas con mail.wyny.com.mx)
- Autenticación PLAIN
- CC automático a cesar_iracheta@wyny.com.mx
- Emails con formato HTML
- Link de token incluido en cada notificación

[Histórico de Pruebas]
2026-06-28: Puerto 25 con TLS - NO funcionó
2026-06-28: Puerto 587 sin TLS - ✓ FUNCIONA CORRECTAMENTE

[Cambios Futuros]
Para cambiar la configuración:
1. Editar setup_servidor.ps1 (líneas 18-24)
2. Editar app/routes/he_control.py (línea ~426)
3. Reiniciar el servidor: python runserver.py
