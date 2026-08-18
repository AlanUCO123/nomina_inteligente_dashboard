import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("BÚSQUEDA: Primer evento PENDIENTE de Verónica (supervisor 10036)")
print("="*100 + "\n")

query = text("""
    SELECT TOP 5
        id,
        numero_empleado,
        supervisor_numero,
        estatus,
        fecha_operativa
    FROM ni_he_eventos_jornada
    WHERE supervisor_numero = 10036
      AND estatus = 'PENDIENTE'
      AND fecha_operativa >= '2026-06-24'
      AND fecha_operativa <= '2026-06-30'
    ORDER BY id
""")

with engine.connect() as conn:
    results = conn.execute(query).mappings().all()
    
    if results:
        print(f"Encontrados {len(results)} eventos PENDIENTE de Verónica:")
        print()
        for idx, row in enumerate(results, 1):
            print(f"{idx}. Evento ID: {row['id']}")
            print(f"   Empleado: {row['numero_empleado']}")
            print(f"   Supervisor: {row['supervisor_numero']}")
            print(f"   Estatus: {row['estatus']}")
            print()
        
        first_id = results[0]['id']
        print(f"✅ Usar evento_id={first_id} para el test positivo")
    else:
        print("❌ No se encontraron eventos PENDIENTE de Verónica")

print()
