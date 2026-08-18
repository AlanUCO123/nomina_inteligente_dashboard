import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("VERIFICACIÓN: Logs de acciones en ni_he_eventos_jornada_log")
print("="*100 + "\n")

query = text("""
    SELECT TOP 30
        l.id,
        l.evento_base_id,
        l.accion,
        l.usuario,
        l.respondido_por,
        l.fecha_accion,
        e.supervisor_numero
    FROM ni_he_eventos_jornada_log l
    LEFT JOIN ni_he_eventos_jornada e ON e.id = l.evento_base_id
    WHERE l.semana_piloto = '2026-06-24_2026-06-30'
    ORDER BY l.fecha_accion DESC
""")

with engine.connect() as conn:
    result = conn.execute(query).mappings().all()
    
    if result:
        print(f"{'ID':<6} {'Evento':<8} {'Acción':<15} {'Usuario':<12} {'Respondido':<12} {'Supervisor':<12} {'Fecha':<20}")
        print("-" * 100)
        
        for row in result:
            evento = str(row['evento_base_id']) if row['evento_base_id'] else '-'
            accion = str(row['accion'])[:14] if row['accion'] else '-'
            usuario = str(row['usuario']) if row['usuario'] else '-'
            respondido = str(row['respondido_por']) if row['respondido_por'] else '-'
            supervisor = str(row['supervisor_numero']) if row['supervisor_numero'] else '-'
            fecha = str(row['fecha_accion'])[:19] if row['fecha_accion'] else '-'
            
            print(f"{str(row['id']):<6} {evento:<8} {accion:<15} {usuario:<12} {respondido:<12} {supervisor:<12} {fecha:<20}")
    else:
        print("❌ No hay registros en el log")

print("\n✓ Búsqueda completada\n")
