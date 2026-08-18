from app.database import engine
from sqlalchemy import text

# Ver columnas de la tabla
query = text("""
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ni_empleados_maestro'
ORDER BY ORDINAL_POSITION
""")

print("Columnas de ni_empleados_maestro:")
with engine.connect() as conn:
    results = conn.execute(query)
    for row in results.fetchall():
        print(f"  - {row[0]:30} ({row[1]})")
