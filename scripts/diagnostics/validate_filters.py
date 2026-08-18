import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("VALIDACIÓN: Datos vistos por Verónica (supervisor 10036)")
print("="*100)

query_veronica = text("""
    SELECT
        supervisor_numero,
        supervisor_nombre,
        departamento,
        COUNT(*) AS eventos,
        COUNT(DISTINCT numero_empleado) AS empleados,
        CAST(SUM(minutos_finales) / 60.0 AS DECIMAL(10,2)) AS horas
    FROM vw_ni_he_eventos_resumen
    WHERE semana_piloto = '2026-06-24_2026-06-30'
      AND supervisor_numero = '10036'
    GROUP BY
        supervisor_numero,
        supervisor_nombre,
        departamento
""")

with engine.connect() as conn:
    result = conn.execute(query_veronica).mappings().all()
    
    if result:
        print(f"\n{'Supervisor':<20} {'Nombre':<30} {'Departamento':<15} {'Eventos':<10} {'Empleados':<10} {'Horas':<10}")
        print("-" * 100)
        
        for row in result:
            print(f"{str(row['supervisor_numero']):<20} {str(row['supervisor_nombre']):<30} {str(row['departamento']):<15} {str(row['eventos']):<10} {str(row['empleados']):<10} {str(row['horas']):<10}")
    else:
        print("❌ No hay registros para supervisor 10036")

print("\n" + "="*100)
print("VALIDACIÓN: Todos los datos (sin filtro)")
print("="*100)

query_todos = text("""
    SELECT
        COUNT(*) AS eventos,
        COUNT(DISTINCT numero_empleado) AS empleados,
        COUNT(DISTINCT CASE WHEN estatus = 'PENDIENTE' THEN evento_base_id END) AS pendientes,
        CAST(SUM(minutos_finales) / 60.0 AS DECIMAL(10,2)) AS horas
    FROM vw_ni_he_eventos_resumen
    WHERE semana_piloto = '2026-06-24_2026-06-30'
""")

with engine.connect() as conn:
    result = conn.execute(query_todos).mappings().first()
    
    if result:
        print(f"\nEventos:    {result['eventos']}")
        print(f"Empleados:  {result['empleados']}")
        print(f"Pendientes: {result['pendientes']}")
        print(f"Horas:      {result['horas']}")

print("\n✓ Validación completada\n")
