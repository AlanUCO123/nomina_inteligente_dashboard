from app.database import engine
from sqlalchemy import text

# Buscar tablas que contengan "supervisor"
query = text("""
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME LIKE '%supervisor%'
ORDER BY TABLE_NAME
""")

with engine.connect() as conn:
    results = conn.execute(query)
    tables = results.fetchall()
    
    if tables:
        print("✓ Tablas encontradas:")
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("✗ No se encontraron tablas con 'supervisor'")
        
        # Listar todas las tablas
        print("\nTodas las tablas disponibles:")
        all_tables = text("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_NAME")
        results = conn.execute(all_tables)
        for table in results.fetchall():
            print(f"  - {table[0]}")
