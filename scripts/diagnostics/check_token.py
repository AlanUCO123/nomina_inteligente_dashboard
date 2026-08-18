from app.database import engine
from sqlalchemy import text

query = text("""
SELECT TOP 5
    token,
    supervisor_numero,
    supervisor_nombre,
    departamento,
    fecha_inicio,
    fecha_fin,
    activo,
    fecha_expiracion,
    ultimo_acceso
FROM ni_he_tokens_revision
WHERE supervisor_numero = '10036'
ORDER BY fecha_creacion DESC
""")

with engine.connect() as conn:
    results = conn.execute(query)
    print("Tokens para supervisor 10036:")
    print()
    
    for row in results.fetchall():
        print(f"Token: {row[0]}")
        print(f"  Supervisor: {row[1]} ({row[2]})")
        print(f"  Departamento: '{row[3]}'")
        print(f"  Fechas: {row[4]} a {row[5]}")
        print(f"  Activo: {row[6]}, Expira: {row[7]}")
        print(f"  Último acceso: {row[8]}")
        print()
