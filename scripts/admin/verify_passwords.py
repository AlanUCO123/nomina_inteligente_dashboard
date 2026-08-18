import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

query = """
SELECT
    login_user,
    nombre_usuario,
    numero_empleado,
    CASE WHEN password_hash IS NULL THEN 'SIN PASSWORD' ELSE 'CON PASSWORD' END AS password_status,
    requiere_cambio_password,
    activo
FROM ni_usuarios
WHERE login_user IN ('iracheta', '10036');
"""

with engine.connect() as conn:
    result = conn.execute(text(query))
    rows = result.fetchall()
    
    if rows:
        print("\n✓ Resultado del Query:")
        print("─" * 100)
        print(f"{'login_user':<15} {'nombre_usuario':<30} {'numero_empleado':<15} {'password_status':<15} {'requiere_cambio':<15} {'activo':<10}")
        print("─" * 100)
        
        for row in rows:
            print(f"{str(row[0]):<15} {str(row[1]):<30} {str(row[2]):<15} {str(row[3]):<15} {str(row[4]):<15} {str(row[5]):<10}")
        
        print("─" * 100)
        print(f"\n✓ Total de registros: {len(rows)}")
    else:
        print("⚠ No se encontraron registros")
