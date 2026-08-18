import sys
import os
import secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine
from datetime import datetime, timedelta

# Generar token nuevo
token = secrets.token_hex(16)
print(f"Token generado: {token}")

# Crear notificación y token
with engine.begin() as conn:
    # Obtener el supervisor
    supervisor = conn.execute(
        text("""
            SELECT id, numero_empleado, nombre_usuario, email
            FROM ni_usuarios
            WHERE numero_empleado = '10036'
        """)
    ).mappings().first()
    
    if not supervisor:
        print("❌ Supervisor no encontrado")
        exit()
    
    print(f"Supervisor: {supervisor['nombre_usuario']} ({supervisor['numero_empleado']})")
    print(f"Email: {supervisor['email']}")
    
    # Crear token
    fecha_inicio = '2026-06-24'
    fecha_fin = '2026-06-30'
    departamento = 'ACABADO'
    
    conn.execute(
        text("""
            INSERT INTO ni_he_tokens_revision (
                token,
                supervisor_numero,
                fecha_inicio,
                fecha_fin,
                departamento,
                activo,
                fecha_expiracion,
                fecha_creacion
            )
            VALUES (
                :token,
                :supervisor_numero,
                :fecha_inicio,
                :fecha_fin,
                :departamento,
                1,
                DATEADD(DAY, 7, GETDATE()),
                GETDATE()
            )
        """),
        {
            "token": token,
            "supervisor_numero": supervisor['numero_empleado'],
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "departamento": departamento
        }
    )
    
    print("\n✓ Token guardado en BD")
    print(f"  Departamento: {departamento}")
    print(f"  Período: {fecha_inicio} a {fecha_fin}")
    print(f"  Expira en: 7 días")
    print(f"\n🔗 URL de acceso:")
    print(f"http://127.0.0.1:8009/he-control?token={token}")
