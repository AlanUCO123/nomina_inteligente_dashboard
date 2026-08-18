from app.database import engine
from sqlalchemy import text

# Ver columnas de la vista
query = text("""
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'vw_ni_he_eventos_resumen'
ORDER BY ORDINAL_POSITION
""")

print("Columnas de vw_ni_he_eventos_resumen:")
with engine.connect() as conn:
    results = conn.execute(query)
    for row in results.fetchall():
        print(f"  - {row[0]:30} ({row[1]})")
        
    print("\n\nPrimera fila de datos:")
    query2 = text("SELECT TOP 1 * FROM vw_ni_he_eventos_resumen")
    results = conn.execute(query2)
    row = results.fetchone()
    
    if row:
        cols = results.keys()
        for col, val in zip(cols, row):
            print(f"  {col:30} {val}")
