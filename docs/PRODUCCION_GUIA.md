# 📦 GUÍA DE PRODUCCIÓN - NOVA Personal

## ✅ Checklist Previo a Copiar

### 1. **Archivos Necesarios para Producción**
```
nomina_inteligente_dashboard/
├── app/                           ✓ Código principal
├── runserver.py                   ✓ Script para iniciar
├── requirements.txt               ✓ Dependencias
├── .env.example                   ✓ Variables de ejemplo
├── README.md                      ✓ Documentación
├── TROUBLESHOOTING.md             ✓ Solución de problemas
├── SMTP_CONFIG.md                 ✓ Configuración SMTP
└── TOKEN_AUTH_GUIDE.md            ✓ Guía de tokens
```

### 2. **Archivos de Desarrollo a OMITIR** (no necesarios en prod)
```
❌ check_*.py                   # Scripts de diagnóstico
❌ create_test_notification.py  # Generador de pruebas
❌ find_*.py                    # Búsqueda de tablas
❌ get_valid_token.py           # Obtener tokens prueba
❌ test_*.py                    # Tests SMTP
❌ test_*.ps1                   # Scripts PowerShell
❌ verify_*.py                  # Verificadores
❌ CONSOLIDATION_COMPLETE.md    # Documentación desarrollo
❌ QUICK_START.md               # Guía de desarrollo
❌ SMTP_CONFIG_GUIDE.md         # Guía de config (usar SMTP_CONFIG.md)
```

### 3. **Configuración SMTP - VALIDADA ✓**
```
Servidor:     mail.wyny.com.mx
Puerto:       587 (sin TLS)
Usuario:      iracheta09
Contraseña:   Wyny202520262027
De:           iracheta09@wyny.com.mx
CC automático: cesar_iracheta@wyny.com.mx
```

### 4. **Pasos para Copiar a Producción**

#### **Opción A: Copia Manual (Recomendado)**
```powershell
# 1. En servidor de producción
cd C:\app

# 2. Copiar carpeta (sin archivos de desarrollo)
robocopy C:\proyectos\nomina_inteligente_dashboard . /S /XF check_*.py create_test_notification.py find_*.py get_valid_token.py test_*.py test_*.ps1 verify_*.py CONSOLIDATION_COMPLETE.md QUICK_START.md SMTP_CONFIG_GUIDE.md

# 3. Crear entorno virtual
cd nomina_inteligente_dashboard
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Configurar variables de entorno (EN PRODUCCIÓN)
$env:SMTP_SERVER = "mail.wyny.com.mx"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "iracheta09"
$env:SMTP_PASSWORD = "Wyny202520262027"
$env:SMTP_FROM = "iracheta09@wyny.com.mx"

# 5. Iniciar servidor
python runserver.py
```

#### **Opción B: Copia de Carpeta Completa**
```powershell
# Copiar todo (luego eliminar archivos de desarrollo)
robocopy C:\proyectos\nomina_inteligente_dashboard C:\app\nomina_inteligente_dashboard /S /MIR

# Ir a la carpeta y eliminar archivos de desarrollo
cd C:\app\nomina_inteligente_dashboard
Remove-Item check_*.py -Force
Remove-Item test_*.py -Force
Remove-Item verify_*.py -Force
Remove-Item find_*.py -Force
Remove-Item get_valid_token.py -Force
Remove-Item create_test_notification.py -Force
Remove-Item CONSOLIDATION_COMPLETE.md -Force
Remove-Item QUICK_START.md -Force
Remove-Item SMTP_CONFIG_GUIDE.md -Force
```

### 5. **Validación en Producción**

Después de copiar, verifica:

```powershell
# 1. Entorno virtual
.\venv\Scripts\Activate.ps1

# 2. Paquetes instalados
pip list

# 3. Variables de entorno
$env:SMTP_SERVER     # Debe mostrar: mail.wyny.com.mx
$env:SMTP_PORT       # Debe mostrar: 587

# 4. Iniciar servidor
python runserver.py
# Debe mostrar: INFO: Uvicorn running on http://0.0.0.0:8009

# 5. Probar email (en otra ventana)
Invoke-RestMethod -Uri 'http://localhost:8009/he-control/enviar-notificacion-prueba' -Method Post
```

### 6. **Configuración del Servicio (Opcional pero Recomendado)**

Si quieres que se inicie automáticamente como servicio:

```powershell
# Usar NSSM o Task Scheduler para autoinicar
# Crear tarea programada que ejecute:
python.exe C:\app\nomina_inteligente_dashboard\runserver.py

# Alternativamente, usar NSSM (Non-Sucking Service Manager)
# nssm install NovaPersonal "C:\app\nomina_inteligente_dashboard\venv\Scripts\python.exe" "C:\app\nomina_inteligente_dashboard\runserver.py"
```

### 7. **Importante: Variables de Entorno en Producción**

Las variables de entorno deben estar disponibles cuando inicia el servidor:

**OPCIÓN 1: Variables del Sistema (Persistentes)**
- Control Panel → System → Environment Variables
- Agregar las 5 variables SMTP
- Reiniciar servidor o máquina

**OPCIÓN 2: Ejecutar en Script (Temporal)**
```powershell
$env:SMTP_SERVER = "mail.wyny.com.mx"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "iracheta09"
$env:SMTP_PASSWORD = "Wyny202520262027"
$env:SMTP_FROM = "iracheta09@wyny.com.mx"
python runserver.py
```

**OPCIÓN 3: Setup Script (Recomendado)**
- Usa el script `setup_servidor.ps1` incluido
- Lo hace todo automáticamente

---

## 🎯 Resumen Rápido

✅ **Copiar esta carpeta:** `C:\proyectos\nomina_inteligente_dashboard`  
⏸️ **Omitir archivos de desarrollo** (ver arriba)  
⚙️ **Configurar variables SMTP**  
🚀 **Ejecutar:** `python runserver.py`  
📧 **Validar:** Enviar email de prueba  

---

## ⚠️ Cosas Importantes

1. **No cambies el puerto 8009** - Si necesitas otro puerto, actualiza todas las URLs de token
2. **Las variables SMTP deben estar configuradas ANTES de iniciar el servidor**
3. **El usuario iracheta09 debe tener permisos en mail.wyny.com.mx**
4. **Puerto 587 sin TLS** es la configuración correcta (puerto 25 no funcionó)
5. **Los emails se envían a:** Destinatario + CC a cesar_iracheta@wyny.com.mx

---

**¿Listo para copiar? Avísame si necesitas ayuda.** 🚀
