import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("USUARIOS DISPONIBLES PARA LOGIN")
print("="*100 + "\n")

sql = text("""
    SELECT TOP 20
        u.id,
        u.login_user,
        u.numero_empleado,
        e.nombre_completo,
        e.deptop
    FROM ni_usuarios u
    LEFT JOIN ni_empleados_maestro e ON e.numero_empleado = u.numero_empleado
    WHERE u.activo = 1
    ORDER BY u.login_user
""")

sql_roles = text("""
    SELECT r.codigo
    FROM ni_usuario_roles ur
    INNER JOIN ni_roles r ON r.id = ur.rol_id
    WHERE ur.usuario_id = :usuario_id AND ur.activo = 1 AND r.activo = 1
""")

with engine.connect() as conn:
    results = conn.execute(sql).mappings().all()

print(f"{'Usuario':<15} {'No.Emp':<8} {'Nombre':<40} {'Depto':<15} {'Roles':<50}")
print("-" * 130)

for row in results:
    usuario = row['login_user'] or '?'
    num_emp = str(row['numero_empleado']) or '?'
    nombre = (row['nombre_completo'] or '?')[:39]
    depto = (row['deptop'] or '?')[:14]
    
    # Obtener roles
    with engine.connect() as conn:
        roles_result = conn.execute(sql_roles, {"usuario_id": row['id']}).scalars().all()
    roles = ', '.join(roles_result) if roles_result else 'SIN ROLES'
    roles = roles[:49]
    
    print(f"{usuario:<15} {num_emp:<8} {nombre:<40} {depto:<15} {roles:<50}")

print("\n" + "="*100)
print("CONTRASEÑA PARA TODOS LOS USUARIOS: Nova2026*")
print("="*100 + "\n")

print("EJEMPLOS DE USO:")
print("""
✅ ADMIN (acceso total):
   - Usuario: iracheta
   - Contraseña: Nova2026*
   - Verá: 198 eventos, 138 empleados, todos los filtros

✅ SUPERVISOR (solo su equipo):
   - Usuario: 10036 o 10036 (Verónica)
   - Contraseña: Nova2026*
   - Verá: 27 eventos, 19 empleados, solo su departamento (ACABADO)

✅ OTROS usuarios en la lista arriba
   - Contraseña: Nova2026*
""")

print()
