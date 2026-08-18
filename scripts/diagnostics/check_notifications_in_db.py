from app.database import engine
from sqlalchemy import text

query = text("""
SELECT TOP 5 
    id,
    destino,
    asunto,
    mensaje,
    supervisor_nombre,
    estatus,
    fecha_envio
FROM ni_he_notificaciones_revision
WHERE supervisor_numero = '10036'
ORDER BY id DESC
""")

with engine.connect() as conn:
    result = conn.execute(query)
    notifs = result.mappings().all()
    
    if notifs:
        print("\n" + "=" * 100)
        print("NOTIFICACIONES EN BD".center(100))
        print("=" * 100)
        for notif in notifs:
            print(f"\nID {notif['id']}:")
            print(f"  Destino:    {notif['destino']}")
            print(f"  Asunto:     {notif['asunto']}")
            print(f"  Mensaje:    {notif['mensaje'][:100] if notif['mensaje'] else 'NULL'}")
            print(f"  Estatus:    {notif['estatus']}")
            print(f"  Fecha Env:  {notif['fecha_envio']}")
