import sys
import os
import hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

def hash_password(password):
    """Genera hash SHA256 de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

# Datos del usuario a crear/actualizar
login_user = "50055"
password_temporal = "Nova2026*"
password_hash = hash_password(password_temporal)

print("=" * 60)
print("CONFIGURANDO USUARIO 50055 COMO ADMIN")
print("=" * 60)

with engine.begin() as conn:
    # 1. Verificar si el usuario existe
    user_check = conn.execute(
        text("""
            SELECT id, nombre_usuario, activo
            FROM ni_usuarios
            WHERE login_user = :login_user
        """),
        {"login_user": login_user}
    ).mappings().first()
    
    if not user_check:
        print(f"\n✗ El usuario {login_user} NO existe en la base de datos")
        print("Necesitas crear el usuario primero.")
        sys.exit(1)
    
    usuario_id = user_check["id"]
    print(f"\n✓ Usuario encontrado: ID={usuario_id}, Nombre={user_check['nombre_usuario']}")
    
    # 2. Actualizar contraseña
    conn.execute(
        text("""
            UPDATE ni_usuarios
            SET password_hash = :password_hash,
                requiere_cambio_password = 1,
                fecha_actualizacion = GETDATE(),
                activo = 1
            WHERE login_user = :login_user
        """),
        {
            "password_hash": password_hash,
            "login_user": login_user
        }
    )
    print(f"✓ Contraseña actualizada")
    
    # 3. Obtener ID del rol ADMIN
    admin_role = conn.execute(
        text("""
            SELECT id
            FROM ni_roles
            WHERE codigo = 'ADMIN' AND activo = 1
        """)
    ).scalar()
    
    if not admin_role:
        print("✗ No se encontró el rol ADMIN en la BD")
        sys.exit(1)
    
    print(f"✓ Rol ADMIN encontrado: ID={admin_role}")
    
    # 4. Verificar si el usuario ya tiene el rol ADMIN
    existing_role = conn.execute(
        text("""
            SELECT id
            FROM ni_usuario_roles
            WHERE usuario_id = :usuario_id
              AND rol_id = :rol_id
        """),
        {"usuario_id": usuario_id, "rol_id": admin_role}
    ).scalar()
    
    if existing_role:
        print(f"✓ El usuario ya tiene el rol ADMIN")
    else:
        # 5. Asignar rol ADMIN
        conn.execute(
            text("""
                INSERT INTO ni_usuario_roles (usuario_id, rol_id, activo)
                VALUES (:usuario_id, :rol_id, 1)
            """),
            {"usuario_id": usuario_id, "rol_id": admin_role}
        )
        print(f"✓ Rol ADMIN asignado al usuario")

print("\n" + "=" * 60)
print("✓ CONFIGURACIÓN COMPLETADA")
print("=" * 60)
print(f"\nCredenciales de acceso:")
print(f"  Usuario: {login_user}")
print(f"  Contraseña: {password_temporal}")
print(f"  Rol: ADMIN")
print("=" * 60)
