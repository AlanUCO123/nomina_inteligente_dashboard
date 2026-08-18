import sys
import os
import hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

def hash_password(password):
    """Genera hash simple SHA256 de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

password_temporal = "Nova2026*"
password_hash = hash_password(password_temporal)

usuarios = ["iracheta", "10036"]

with engine.begin() as conn:
    for login_user in usuarios:
        conn.execute(
            text("""
                UPDATE ni_usuarios
                SET password_hash = :password_hash,
                    requiere_cambio_password = 1,
                    fecha_actualizacion = GETDATE()
                WHERE login_user = :login_user
            """),
            {
                "password_hash": password_hash,
                "login_user": login_user
            }
        )

print("✓ Passwords actualizados para:", usuarios)
print(f"Contraseña temporal: {password_temporal}")
print("\nCredenciales de prueba:")
print("─" * 50)
for user in usuarios:
    print(f"Usuario: {user}")
    print(f"Password: {password_temporal}")
    print()
