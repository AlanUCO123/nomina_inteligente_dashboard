import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_AUTH_TYPE = os.getenv("DB_AUTH_TYPE", "sql")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

print("=" * 60)
print("DIAGNÓSTICO DE CONEXIÓN SQL SERVER")
print("=" * 60)
print(f"✓ Servidor:      {DB_SERVER}")
print(f"✓ Base datos:    {DB_NAME}")
print(f"✓ Autenticación: {DB_AUTH_TYPE.upper()}")
if DB_AUTH_TYPE.lower() != "windows":
    print(f"✓ Usuario:       {DB_USER}")
print(f"✓ Driver:        {DB_DRIVER}")
print("=" * 60)

# Construir conexión directa con pyodbc
if DB_AUTH_TYPE.lower() == "windows":
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
else:
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )

print("\nIntentando conectar...")
try:
    conn = pyodbc.connect(connection_string, timeout=5)
    cursor = conn.cursor()
    
    # Probar consulta simple
    cursor.execute("SELECT @@VERSION")
    version = cursor.fetchone()
    print(f"✅ CONEXIÓN EXITOSA")
    print(f"   SQL Server Version: {version[0]}")
    
    # Verificar vistas
    cursor.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS 
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME LIKE 'vw_ni%'
    """)
    vistas = cursor.fetchall()
    print(f"\n✅ Vistas encontradas:")
    for vista in vistas:
        print(f"   - {vista[0]}")
    
    if not vistas:
        print("   ⚠️  No se encontraron vistas vw_ni_*")
    
    conn.close()
    
except pyodbc.Error as e:
    print(f"❌ ERROR DE CONEXIÓN")
    print(f"   {e}")
    print(f"\n📋 Posibles causas:")
    print(f"   1. Usuario/contraseña incorrectos")
    print(f"   2. Usuario no existe en SQL Server")
    print(f"   3. Servidor no disponible o firewall bloqueado")
    print(f"   4. Base de datos no existe")
except Exception as e:
    print(f"❌ ERROR INESPERADO: {e}")
