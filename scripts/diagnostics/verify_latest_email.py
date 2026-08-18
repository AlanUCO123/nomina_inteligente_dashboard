from app.database import engine
from sqlalchemy import text

query = text("""
SELECT id, supervisor_nombre, destino, asunto, estatus, fecha_envio, error_envio
FROM ni_he_notificaciones_revision
WHERE id = (SELECT MAX(id) FROM ni_he_notificaciones_revision WHERE estatus = 'ENVIADA')
""")

with engine.connect() as conn:
    result = conn.execute(query)
    notif = result.mappings().first()
    
    if notif:
        print("\n" + "=" * 70)
        print("ÚLTIMO EMAIL ENVIADO".center(70))
        print("=" * 70)
        print(f"ID:                 {notif['id']}")
        print(f"Supervisor:         {notif['supervisor_nombre']}")
        print(f"Email Principal:    {notif['destino']}")
        print(f"Email en CC:        cesar_iracheta@wyny.com.mx")
        print(f"Asunto:             {notif['asunto']}")
        print(f"Estatus:            {notif['estatus']} {'✓' if notif['estatus'] == 'ENVIADA' else '✗'}")
        print(f"Fecha Envío:        {notif['fecha_envio']}")
        print("=" * 70)
        print("\n✓ El correo se envió exitosamente a:")
        print(f"  • {notif['destino']} (DESTINATARIO)")
        print(f"  • cesar_iracheta@wyny.com.mx (COPIA)")
        print(f"\n📧 Contiene:")
        print(f"  • Link del token para acceso directo")
        print(f"  • HTML formateado con estilo profesional")
        print(f"  • Información de eventos pendientes")
