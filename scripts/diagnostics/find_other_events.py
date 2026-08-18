import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*120)
print("BÚSQUEDA: Eventos que NO son de Verónica (supervisor 10036)")
print("="*120 + "\n")

query = text("""
    SELECT TOP 10
        evento_base_id,
        numero_empleado,
        nombre_completo,
        supervisor_numero,
        supervisor_nombre,
        horas_finales,
        estatus
    FROM vw_ni_he_eventos_resumen
    WHERE semana_piloto = '2026-06-24_2026-06-30'
      AND supervisor_numero <> '10036'
    ORDER BY evento_base_id
""")

with engine.connect() as conn:
    result = conn.execute(query).mappings().all()
    
    if result:
        print(f"{'ID':<8} {'Empleado':<15} {'Nombre':<30} {'Supervisor':<12} {'Nombre Super':<25} {'Horas':<8} {'Estatus':<12}")
        print("-" * 120)
        
        for row in result:
            print(f"{str(row['evento_base_id']):<8} {str(row['numero_empleado']):<15} {str(row['nombre_completo'][:29]):<30} {str(row['supervisor_numero']):<12} {str(row['supervisor_nombre'][:24]):<25} {str(row['horas_finales']):<8} {str(row['estatus']):<12}")
        
        print("\n✓ Usa cualquiera de estos evento_base_id para la prueba negativa")
    else:
        print("❌ No hay eventos de otros supervisores")

print()
