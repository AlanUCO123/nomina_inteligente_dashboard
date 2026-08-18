import requests

session = requests.Session()

# Login como iracheta
print("Intentando login como iracheta...")
r = session.post(
    "http://127.0.0.1:8009/login",
    data={"login_user": "iracheta", "password": "Nova2026*"},
    allow_redirects=False
)

print(f"Status: {r.status_code}")
print(f"Redirect: {r.headers.get('location', 'N/A')}")

# Acceder a /home
print("\nAccediendo a /home...")
r = session.get("http://127.0.0.1:8009/home")
print(f"Status: {r.status_code}")

if r.status_code == 200:
    # Verificar que tiene los KPIs
    if "Eventos HE" in r.text and "Pendientes" in r.text:
        print("✅ KPIs cargados correctamente")
        if "198" in r.text:
            print("✅ Eventos = 198 (Admin iracheta viendo todos)")
    else:
        print("❌ KPIs no encontrados")
else:
    print(f"❌ Error: {r.status_code}")

print("\n" + "="*60)
print("Ahora probando con 10036 (Verónica, SUPERVISOR)...")
print("="*60)

session2 = requests.Session()
r = session2.post(
    "http://127.0.0.1:8009/login",
    data={"login_user": "10036", "password": "Nova2026*"},
    allow_redirects=False
)

print(f"Login status: {r.status_code}")

r = session2.get("http://127.0.0.1:8009/home")
print(f"Home status: {r.status_code}")

if r.status_code == 200:
    if "Eventos HE" in r.text and "Pendientes" in r.text:
        print("✅ KPIs cargados correctamente")
        if "27" in r.text:
            print("✅ Eventos = 27 (Supervisor 10036 solo su equipo)")
    else:
        print("❌ KPIs no encontrados")
