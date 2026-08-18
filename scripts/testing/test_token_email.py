#!/usr/bin/env python3
"""
Script para probar token + email con supervisor 10036
Genera token, crea notificación, envía email, muestra link para probar
"""

import os
import sys
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import text

# Agregar directorio al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine

# Colores para terminal
def print_success(msg):
    print(f"\033[92m✓ {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m✗ {msg}\033[0m")

def print_info(msg):
    print(f"\033[94mℹ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m⚠ {msg}\033[0m")

def print_header(msg):
    print(f"\n\033[96m{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\033[0m\n")

# ============================================================================
# PASO 1: Obtener datos del supervisor 10036
# ============================================================================

print_header("PASO 1: Obtener datos del supervisor 10036")

try:
    with engine.connect() as conn:
        # Obtener supervisor
        supervisor_query = text("""
            SELECT TOP 1 
                numero_empleado, 
                nombre_completo, 
                deptop,
                email
            FROM ni_empleados_maestro 
            WHERE numero_empleado = '10036'
        """)
        
        result = conn.execute(supervisor_query)
        supervisor = result.fetchone()
        
        if not supervisor:
            print_error("Supervisor 10036 no encontrado en BD")
            sys.exit(1)
        
        supervisor_numero = supervisor[0]
        supervisor_nombre = supervisor[1]
        departamento = supervisor[2]
        supervisor_email = supervisor[3]
        
        print_success(f"Número: {supervisor_numero}")
        print_success(f"Nombre: {supervisor_nombre}")
        print_success(f"Departamento: {departamento}")
        print_success(f"Email: {supervisor_email}")
        
except Exception as e:
    print_error(f"Error consultando BD: {e}")
    sys.exit(1)

# ============================================================================
# PASO 2: Generar token
# ============================================================================

print_header("PASO 2: Generar token único")

token = secrets.token_hex(16)  # 32 caracteres hexadecimales
fecha_inicio = "2026-06-24"
fecha_fin = "2026-06-30"
semana_piloto = "2026-06-24_2026-06-30"

print_success(f"Token generado: {token}")
print_info(f"Período: {fecha_inicio} al {fecha_fin}")
print_info(f"Semana piloto: {semana_piloto}")

# ============================================================================
# PASO 3: Insertar token en BD
# ============================================================================

print_header("PASO 3: Guardar token en BD")

try:
    with engine.connect() as conn:
        fecha_expiracion = datetime.now() + timedelta(days=7)
        
        insert_token = text("""
            INSERT INTO ni_he_tokens_revision (
                token,
                supervisor_numero,
                supervisor_nombre,
                supervisor_email,
                departamento,
                fecha_inicio,
                fecha_fin,
                semana_piloto,
                rol_acceso,
                activo,
                fecha_creacion,
                fecha_expiracion
            ) VALUES (
                :token,
                :supervisor_numero,
                :supervisor_nombre,
                :supervisor_email,
                :departamento,
                :fecha_inicio,
                :fecha_fin,
                :semana_piloto,
                'SUPERVISOR',
                1,
                GETDATE(),
                :fecha_expiracion
            )
        """)
        
        conn.execute(insert_token, {
            "token": token,
            "supervisor_numero": supervisor_numero,
            "supervisor_nombre": supervisor_nombre,
            "supervisor_email": supervisor_email,
            "departamento": departamento,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "semana_piloto": semana_piloto,
            "fecha_expiracion": fecha_expiracion
        })
        
        conn.commit()
        print_success(f"Token guardado en BD (activo hasta {fecha_expiracion.strftime('%Y-%m-%d %H:%M')})")
        
except Exception as e:
    print_error(f"Error insertando token: {e}")
    sys.exit(1)

# ============================================================================
# PASO 4: Crear notificación PENDIENTE
# ============================================================================

print_header("PASO 4: Crear notificación PENDIENTE en BD")

try:
    with engine.connect() as conn:
        # Contar HE pendiente del supervisor
        count_query = text("""
            SELECT ISNULL(COUNT(*), 0) 
            FROM ni_he_eventos_jornada
            WHERE departamento = :depto
            AND estatus = 'PENDIENTE'
            AND CAST(fecha_operativa AS DATE) BETWEEN :fecha_inicio AND :fecha_fin
        """)
        
        result = conn.execute(count_query, {
            "depto": departamento,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin
        })
        
        cant_eventos = result.scalar() or 0
        
        link_acceso = f"http://192.168.39.122:8009/he-control?token={token}"
        
        mensaje = f"""Buen día {supervisor_nombre},

Como parte del piloto de Control HE en Línea NOVA, se han detectado {cant_eventos} horas extra pendientes de revisión en su departamento ({departamento}).

Período: {fecha_inicio} al {fecha_fin}

Por favor ingrese al portal para:
✓ Confirmar horas extra válidas
✓ Rechazar horas extra con error
✓ Ajustar horas extra si es necesario
✓ Agregar horas extra manual si falta alguna

Link de acceso (válido por 7 días):
{link_acceso}

Esta revisión es paralela al sistema actual y nos ayudará a validar el nuevo flujo antes de llevarlo a operación formal.

Agradecemos su participación en la prueba piloto.

---
NOVA - Sistema de Nómina Inteligente
Soporte: sistemas@wyny.mx"""
        
        insert_notification = text("""
            INSERT INTO ni_he_notificaciones_revision (
                fecha_inicio,
                fecha_fin,
                supervisor_numero,
                supervisor_nombre,
                departamento,
                destino,
                asunto,
                eventos_pendientes,
                empleados,
                minutos_detectados,
                estatus,
                fecha_creacion,
                mensaje
            ) VALUES (
                :fecha_inicio,
                :fecha_fin,
                :supervisor_numero,
                :supervisor_nombre,
                :departamento,
                :destino,
                :asunto,
                :eventos_pendientes,
                :empleados,
                :minutos_detectados,
                'PENDIENTE',
                GETDATE(),
                :mensaje
            )
        """)
        
        asunto = f"Control HE en Línea - Piloto ACABADO ({cant_eventos} eventos)"
        
        result = conn.execute(insert_notification, {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "supervisor_numero": supervisor_numero,
            "supervisor_nombre": supervisor_nombre,
            "departamento": departamento,
            "destino": supervisor_email,
            "asunto": asunto,
            "eventos_pendientes": cant_eventos,
            "empleados": cant_eventos,  # Por ahora mismo valor
            "minutos_detectados": cant_eventos * 60,  # Convertir a minutos (1 evento = 1 hora = 60 min)
            "mensaje": mensaje
        })
        
        conn.commit()
        
        # Obtener el ID de la notificación insertada
        notif_id_query = text("""
            SELECT TOP 1 id FROM ni_he_notificaciones_revision
            WHERE supervisor_numero = :sup_num AND estatus = 'PENDIENTE'
            ORDER BY fecha_creacion DESC
        """)
        
        result = conn.execute(notif_id_query, {"sup_num": supervisor_numero})
        notif_id = result.scalar()
        
        print_success(f"Notificación creada (ID: {notif_id})")
        print_info(f"Asunto: {asunto}")
        print_info(f"Eventos pendientes: {cant_eventos}")
        print_info(f"Destino: {supervisor_email}")
        
except Exception as e:
    print_error(f"Error creando notificación: {e}")
    sys.exit(1)

# ============================================================================
# PASO 5: Enviar email por SMTP
# ============================================================================

print_header("PASO 5: Enviar email por SMTP")

try:
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "nova@wyny.mx")
    
    if not smtp_user or not smtp_password:
        print_warning("Variables SMTP_USER o SMTP_PASSWORD no configuradas")
        print_warning("Saltando envío de email (puedes hacerlo manualmente después)")
        print_info("Para configurar, ejecuta:")
        print_info("  $env:SMTP_USER = 'tu@gmail.com'")
        print_info("  $env:SMTP_PASSWORD = 'tu_contraseña_app'")
    else:
        print_info(f"Conectando a {smtp_server}:{smtp_port} como {smtp_user}...")
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = supervisor_email
        msg['Subject'] = asunto
        
        msg.attach(MIMEText(mensaje, 'plain', 'utf-8'))
        
        # Enviar
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print_success(f"Email enviado a {supervisor_email}")
        
        # Marcar como ENVIADA en BD
        with engine.connect() as conn:
            update_notif = text("""
                UPDATE ni_he_notificaciones_revision
                SET estatus = 'ENVIADA', fecha_envio = GETDATE()
                WHERE id = :notif_id
            """)
            
            conn.execute(update_notif, {"notif_id": notif_id})
            conn.commit()
            
        print_success("Notificación marcada como ENVIADA en BD")
        
except smtplib.SMTPException as e:
    print_error(f"Error SMTP: {e}")
    print_warning("Email no se envió, pero token y notificación están listos")
except Exception as e:
    print_error(f"Error: {e}")
    sys.exit(1)

# ============================================================================
# PASO 6: Resumen y link de prueba
# ============================================================================

print_header("✅ PRUEBA LISTA")

print(f"""
Link para probar (copiar en navegador):

\033[1;92m{link_acceso}\033[0m

Qué debería suceder cuando lo abras:
  1. ✓ Carga el panel sin pedir login
  2. ✓ Filtros se cargan automáticamente:
     - Fecha inicio: 24/06/2026
     - Fecha fin: 30/06/2026
     - Departamento: {departamento}
  3. ✓ Muestra {cant_eventos} eventos
  4. ✓ Supervisor puede confirmar/rechazar/ajustar

Supervisor:
  - Nombre: {supervisor_nombre}
  - Número: {supervisor_numero}
  - Email: {supervisor_email}
  - Token: {token}

Para verificar en BD (después de hacer acciones):
  SELECT supervisor_nombre, email, ultimo_acceso FROM ni_he_tokens_revision
  WHERE token = '{token}';
  
  SELECT estatus, fecha_envio, fecha_respuesta FROM ni_he_notificaciones_revision
  WHERE supervisor_numero = {supervisor_numero}
  ORDER BY fecha_creacion DESC;
""")

print_header("💡 SIGUIENTES PASOS")

print("""
1. Abre el link en navegador (arriba)
2. Verifica que cargue el panel correcto
3. Intenta confirmar/rechazar un evento
4. Ejecuta SQL SELECT para verificar auditoría
5. Revisa el email recibido (si se envió)
""")
