from app.database import engine
from sqlalchemy import text

# Crear nueva notificación de prueba
insert_query = text("""
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
    '2026-06-24',
    '2026-06-30',
    '10036',
    'ARANDA MORENO VERONICA',
    'ACABADO',
    'veronica_aranda@wyny.com.mx',
    'PRUEBA SMTP - Control HE en Línea',
    31,
    138,
    1860,
    'PENDIENTE',
    GETDATE(),
    'Prueba de envío de notificación por SMTP. Este es un correo de prueba del sistema NOVA de Control de HE.'
)
""")

with engine.connect() as conn:
    conn.execute(insert_query)
    conn.commit()
    
print("✓ Nueva notificación PENDIENTE creada")

# Verificar
verify_query = text("""
SELECT TOP 1 id, supervisor_nombre, destino, asunto, estatus 
FROM ni_he_notificaciones_revision 
WHERE estatus = 'PENDIENTE'
ORDER BY id DESC
""")

with engine.connect() as conn:
    result = conn.execute(verify_query)
    notif = result.mappings().first()
    
    if notif:
        print(f"\nNotificación ID: {notif['id']}")
        print(f"Supervisor: {notif['supervisor_nombre']}")
        print(f"Destino: {notif['destino']}")
        print(f"Asunto: {notif['asunto']}")
        print(f"Estatus: {notif['estatus']}")
