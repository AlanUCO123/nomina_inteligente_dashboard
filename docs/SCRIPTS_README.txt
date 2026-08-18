═══════════════════════════════════════════════════════════════════════════════
SCRIPTS DE EJECUCIÓN - SERVIDOR NÓMINA INTELIGENTE DASHBOARD
═══════════════════════════════════════════════════════════════════════════════

ARCHIVOS DISPONIBLES:

1. start_server.bat
   ─────────────────
   Descripción: Script básico para iniciar el servidor
   Puerto: 8009 (fijo)
   Uso: Doble clic o ejecutar desde cmd
   
   Ejemplo:
   > start_server.bat


2. start_server_custom.bat
   ───────────────────────
   Descripción: Script que permite especificar un puerto personalizado
   Puerto: Personalizado (parámetro)
   Uso: Ejecutar con número de puerto como parámetro
   
   Ejemplos:
   > start_server_custom.bat 8010
   > start_server_custom.bat 3000
   > start_server_custom.bat (usa 8009 si no especifica puerto)


3. start_server_autofix.bat
   ────────────────────────
   Descripción: Script con reinicio automático ante errores y logging
   Puerto: 8009 (fijo)
   Características:
      - Reintentos automáticos si el servidor falla
      - Crea logs en carpeta "logs\"
      - Registra fecha/hora de cada ejecución
   Uso: Doble clic o ejecutar desde cmd
   
   Ejemplo:
   > start_server_autofix.bat
   
   Logs generados: logs\server_2026-07-14_14-30.log


═══════════════════════════════════════════════════════════════════════════════
INSTRUCCIONES DE USO
═══════════════════════════════════════════════════════════════════════════════

OPCIÓN 1: Ejecución Rápida (Recomendado para desarrollo)
──────────────────────────────────────────────────────
1. Abre el Explorador de Archivos
2. Navega a: C:\proyectos\nomina_inteligente_dashboard
3. Doble clic en: start_server.bat
4. Espera el mensaje "Application startup complete"
5. Abre navegador en: http://localhost:8009


OPCIÓN 2: Ejecución con Puerto Personalizado
──────────────────────────────────────────────
1. Abre Símbolo del Sistema (cmd)
2. Navega a: cd C:\proyectos\nomina_inteligente_dashboard
3. Ejecuta: start_server_custom.bat 8010
4. Espera el mensaje "Application startup complete"
5. Abre navegador en: http://localhost:8010


OPCIÓN 3: Ejecución con Reinicio Automático (Producción)
─────────────────────────────────────────────────────────
1. Doble clic en: start_server_autofix.bat
2. La ventana permanecerá abierta
3. Si hay error, reinicia automáticamente
4. Los logs se guardan en: logs\


CREAR ACCESO DIRECTO EN ESCRITORIO
───────────────────────────────────
1. Click derecho en: start_server.bat
2. Selecciona: "Enviar a" > "Escritorio (crear acceso directo)"
3. Renombra el acceso directo si lo deseas
5. Ya puedes ejecutar desde escritorio con doble clic


═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Problema: "Python no reconocido"
Solución: 
  - Verifica que Python esté instalado en C:\Users\<tu_usuario>\AppData\Local\Programs\Python\
  - O instala Python desde python.org
  - Reinicia cmd si ya estaba abierto

Problema: "Puerto ya está en uso"
Solución:
  - Usa start_server_custom.bat con otro puerto
  - O cierra la aplicación que usa ese puerto
  - Comando para ver puertos: netstat -ano | findstr :8009

Problema: "ModuleNotFoundError"
Solución:
  - Asegúrate de estar en el directorio correcto
  - Reinstala dependencias: pip install -r requirements.txt

Problema: Servidor no inicia
Solución:
  - Verifica archivo .env existe en C:\proyectos\nomina_inteligente_dashboard
  - Revisa que la BD esté accesible
  - Checa logs en carpeta logs\ (si usas autofix)


═══════════════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Puerto Defecto: 8009
URL: http://localhost:8009
Framework: FastAPI + Uvicorn
Ubicación: C:\proyectos\nomina_inteligente_dashboard
Archivo Principal: runserver.py

Cuando veas este mensaje, el servidor está listo:
  "Uvicorn running on http://0.0.0.0:8009"

═══════════════════════════════════════════════════════════════════════════════
