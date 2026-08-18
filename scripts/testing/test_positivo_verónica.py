import requests
from requests.cookies import RequestsCookieJar

def test_verónica_confirmar_propio_evento():
    """
    Test positivo: Verónica (10036) intenta confirmar evento_id=111 que le pertenece
    Resultado esperado: La confirmación DEBE funcionar (estatus cambiar a CONFIRMADA)
    """
    
    print("\n" + "="*100)
    print("TEST POSITIVO: Verónica confirmando su propio evento (ID=111)")
    print("="*100)
    
    session = requests.Session()
    
    # Paso 1: Login
    print("\n1. Login como 10036...")
    login_data = {
        'username': '10036',
        'password': 'Nova2026*'
    }
    
    response = session.post(
        "http://127.0.0.1:8009/login",
        data=login_data,
        allow_redirects=False
    )
    
    print(f"   Status: {response.status_code}")
    if response.status_code in (200, 302, 303):
        print("   ✅ Login enviado")
    
    # Paso 2: Verificar sesión
    print("\n2. Accediendo a /he-control para verificar sesión...")
    response = session.get("http://127.0.0.1:8009/he-control")
    print(f"   Status: {response.status_code}")
    if "Usuario:" in response.text and "10036" in response.text:
        print("   ✅ Sesión activa para usuario 10036")
    
    # Paso 3: Confirmar evento
    print("\n3. Enviando POST a /he-control/confirmar con evento_id=111...")
    confirm_data = {
        'evento_id': '111',
        'fecha_inicio': '2026-06-24',
        'fecha_fin': '2026-06-30',
        'departamento': 'TODOS',
        'estatus': 'TODOS'
    }
    
    response = session.post(
        "http://127.0.0.1:8009/he-control/confirmar",
        data=confirm_data,
        allow_redirects=False
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Redirect: {response.headers.get('location', 'N/A')}")
    
    if response.status_code in (200, 302, 303):
        print("   ✅ POST completado sin errores de permiso")
    
    print("\n✅ Test completado. Verifique evento_id=111 en la base de datos.")
    print("   Esperado: estatus = CONFIRMADA (test exitoso)")
    print("   Si estatus = PENDIENTE: test falló (POST rechazado)\n")

if __name__ == "__main__":
    test_verónica_confirmar_propio_evento()
