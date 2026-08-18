import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("BÚSQUEDA: Estado del evento_id=1 después del intento de confirmación")
print("="*100 + "\n")

query = text("""
    SELECT
        id,
        numero_empleado,
        supervisor_numero,
        estatus
    FROM ni_he_eventos_jornada
    WHERE id = 1
""")

with engine.connect() as conn:
    result = conn.execute(query).mappings().first()
    
    if result:
        print(f"Evento ID: 1")
        print(f"  Empleado: {result['numero_empleado']}")
        print(f"  Supervisor: {result['supervisor_numero']}")
        print(f"  Estatus: {result['estatus']}")
        print("\n✓ Interpretación:")
        if result['estatus'] == 'CONFIRMADA':
            print("  ❌ ESTATUS = CONFIRMADA → La validación FALLÓ, Verónica NO debería poder confirmar este evento")
        else:
            print(f"  ✅ ESTATUS = {result['estatus']} → La validación funcionó correctamente")
    else:
        print("❌ No se encontró evento_id=1")

print()
