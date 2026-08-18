from app.database import engine
from sqlalchemy import text

# Buscar supervisor 10036
query = text("""
SELECT TOP 1 
    numero_empleado,
    nombre_completo,
    deptop,
    email,
    puesto_intelisis
FROM ni_empleados_maestro
WHERE numero_empleado = '10036' OR numero_empleado = 10036
""")

print("Buscando supervisor 10036...")
with engine.connect() as conn:
    results = conn.execute(query)
    row = results.fetchone()
    
    if row:
        print(f"✓ Encontrado:")
        print(f"  Número: {row[0]}")
        print(f"  Nombre: {row[1]}")
        print(f"  Departamento: {row[2]}")
        print(f"  Email: {row[3]}")
        print(f"  Puesto: {row[4]}")
    else:
        print("✗ Supervisor 10036 no encontrado")
        print("\nBuscando supervisores con número 100xx...")
        
        query2 = text("""
        SELECT TOP 20 numero_empleado, nombre_completo, deptop, email, puesto_intelisis
        FROM ni_empleados_maestro
        WHERE numero_empleado LIKE '100%' AND (puesto_intelisis LIKE '%SUPER%' OR nombre_completo LIKE '%SUPER%')
        ORDER BY numero_empleado
        """)
        
        results = conn.execute(query2)
        rows = results.fetchall()
        
        if rows:
            print("\nSupervisores encontrados:")
            for row in rows:
                print(f"  {row[0]:10} {row[1]:30} {row[2]:15} {row[4]:20}")
        else:
            print("\nBuscando cualquier empleado que empiece con 100...")
            query3 = text("""
            SELECT TOP 20 numero_empleado, nombre_completo, deptop, puesto_intelisis
            FROM ni_empleados_maestro
            WHERE numero_empleado LIKE '100%'
            ORDER BY numero_empleado
            """)
            
            results = conn.execute(query3)
            for row in results.fetchall():
                print(f"  {row[0]:10} {row[1]:30} {row[2]:15} {row[3]:20}")
