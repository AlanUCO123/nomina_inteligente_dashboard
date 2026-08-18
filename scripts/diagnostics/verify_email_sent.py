from app.database import engine
from sqlalchemy import text

query = text("""
SELECT id, supervisor_nombre, destino, asunto, estatus, fecha_envio, error_envio, fecha_creacion
FROM ni_he_notificaciones_revision
WHERE id = 4
""")

with engine.connect() as conn:
    result = conn.execute(query)
    notif = result.mappings().first()
    
    if notif:
        print("=" * 70)
        print("ESTADO DE NOTIFICACIÓN EN BD".center(70))
        print("=" * 70)
        print(f"ID:                 {notif['id']}")
        print(f"Supervisor:         {notif['supervisor_nombre']}")
        print(f"Email:              {notif['destino']}")
        print(f"Asunto:             {notif['asunto']}")
        print(f"Estatus:            {notif['estatus']} {'✓' if notif['estatus'] == 'ENVIADA' else '✗'}")
        print(f"Fecha Envío:        {notif['fecha_envio']}")
        print(f"Error:              {notif['error_envio'] or 'Ninguno'}")
        print(f"Fecha Creación:     {notif['fecha_creacion']}")
        print("=" * 70)
