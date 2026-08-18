import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

print("\n" + "="*100)
print("VERIFICACIÓN: Estado del evento_id=111 después del test positivo")
print("="*100 + "\n")

query = text("""
    SELECT
        id,
        numero_empleado,
        supervisor_numero,
        estatus
    FROM ni_he_eventos_jornada
    WHERE id = 111
""")

with engine.connect() as conn:
    result = conn.execute(query).mappings().first()
    
    if result:
        print(f"Evento ID: 111")
        print(f"  Empleado: {result['numero_empleado']}")
        print(f"  Supervisor: {result['supervisor_numero']}")
        print(f"  Estatus: {result['estatus']}")
        print("\n✓ Interpretación:")
        if result['estatus'] == 'CONFIRMADA':
            print("  ✅ ESTATUS = CONFIRMADA → La autorización funcionó, Verónica PUDO confirmar")
        elif result['estatus'] == 'PENDIENTE':
            print("  ⚠️ ESTATUS = PENDIENTE → La confirmación no se ejecutó (sesión perdida en POST)")
        else:
            print(f"  ? ESTATUS = {result['estatus']} → Estado inesperado")
    else:
        print("❌ No se encontró evento_id=111")

print()
