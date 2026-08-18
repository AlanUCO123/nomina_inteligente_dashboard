from app.database import engine
from sqlalchemy import text

query = text("""
SELECT TOP 1 
    token, 
    departamento, 
    supervisor_numero, 
    activo, 
    fecha_expiracion, 
    ultimo_acceso
FROM ni_he_tokens_revision 
WHERE supervisor_numero = '10036'
    AND activo = 1 
    AND fecha_expiracion >= GETDATE()
ORDER BY fecha_creacion DESC
""")

with engine.connect() as conn:
    result = conn.execute(query)
    token_row = result.mappings().first()
    
    if token_row:
        print("\n" + "=" * 70)
        print("TOKEN VÁLIDO PARA ACCESO".center(70))
        print("=" * 70)
        print(f"Token:              {token_row['token']}")
        print(f"Departamento:       {token_row['departamento']}")
        print(f"Supervisor:         {token_row['supervisor_numero']}")
        print(f"Activo:             {'✓ SÍ' if token_row['activo'] == 1 else '✗ NO'}")
        print(f"Expira:             {token_row['fecha_expiracion']}")
        print(f"Último Acceso:      {token_row['ultimo_acceso']}")
        print("=" * 70)
        print(f"\n🔗 URL CON TOKEN:")
        print(f"http://192.168.39.122:8009/he-control?token={token_row['token']}\n")
    else:
        print("❌ No hay token válido encontrado")
