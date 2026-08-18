from app.database import engine
from sqlalchemy import text

# Ver columnas de la tabla
query = text("""
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'ni_he_eventos_jornada'
ORDER BY ORDINAL_POSITION
""")

print("Columnas de ni_he_eventos_jornada:")
with engine.connect() as conn:
    results = conn.execute(query)
    cols = results.fetchall()
    
    if cols:
        for row in cols:
            print(f"  - {row[0]:30} ({row[1]})")
    
        print("\n\nPrimera fila de datos:")
        query2 = text("SELECT TOP 1 * FROM ni_he_eventos_jornada")
        results = conn.execute(query2)
        row = results.fetchone()
        
        if row:
            cols_names = results.keys()
            for col, val in zip(cols_names, row):
                if val:
                    print(f"  {col:30} {val}")
    else:
        print("No columns found")
