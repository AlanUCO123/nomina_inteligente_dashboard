# Solución de Problemas - Conexión SQL Server

## Error: Login failed for user 'ramonTI' (18456)

**Significado**: Las credenciales SQL son rechazadas.

### Soluciones:

#### 1. Verificar credenciales en SSMS
Abre SQL Server Management Studio e intenta conectar manualmente:
```
Servidor:     192.168.39.150
Autenticación: SQL Server
Usuario:      ramonTI
Contraseña:   Wyny2025
```

Si falla, las credenciales son incorrectas. Contacta a tu admin de IT.

#### 2. Verificar si SQL Server está disponible
En PowerShell:
```powershell
Test-NetConnection 192.168.39.150 -Port 1433
```

Si dice `TcpTestSucceeded: False`, el servidor no es accesible. 

**Posibles causas:**
- IP incorrecta
- Firewall bloqueando (puerto 1433)
- SQL Server no está corriendo
- Problema de red

---

## Error: Unable to complete login process (08001)

**Significado**: No puede conectarse al servidor (problema de red).

### Soluciones:

1. **Verifica conectividad:**
   ```powershell
   ping 192.168.39.150
   telnet 192.168.39.150 1433  # Ctrl+] para salir
   ```

2. **Si el servidor es local:**
   Cambia `.env` a:
   ```
   DB_SERVER=localhost
   DB_NAME=NominaInteligente
   ```

3. **Pide al admin IT:**
   - Confirmar IP correcta del servidor SQL
   - Confirmar puerto SQL Server (usualmente 1433)
   - Abrir puerto en firewall si es necesario

---

## Error: Base de datos no encontrada

Si consigues conectar pero dice "database doesn't exist", verifica que:

```sql
-- Ejecuta en SSMS (como admin)
SELECT name FROM sys.databases WHERE name = 'NominaInteligente'
```

Si no aparece, la base de datos no existe en ese servidor.

---

## Pasos para ejecutar correctamente

1. **Edita `.env` con datos correctos**
2. **Ejecuta diagnóstico:**
   ```bash
   python diagnose.py
   ```
3. **Si diagnóstico es OK, inicia la app:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Accede a:** http://localhost:8000

---

## Contacto con IT

Proporciona esta información:
```
Servidor:     192.168.39.150
Base datos:   NominaInteligente
Usuario:      ramonTI
Error:        Login failed (18456) o Unable to connect (08001)
```
