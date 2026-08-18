# NOVA Personal - Monitor Vivo de Asistencia

Dashboard web funcional conectado a SQL Server `NominaInteligente`.

## Estructura del proyecto

```
nomina_inteligente_dashboard/
├── app/
│   ├── main.py              # Aplicación principal FastAPI
│   ├── database.py          # Conexión a SQL Server
│   ├── routes/
│   │   └── dashboard.py     # Rutas y lógica del dashboard
│   ├── templates/
│   │   ├── base.html        # Template base
│   │   └── dashboard.html   # Template del dashboard
│   └── static/
│       └── styles.css       # Estilos CSS
├── .env                     # Variables de entorno (confidencial)
└── requirements.txt         # Dependencias Python
```

## Configuración

### 1. Actualizar credenciales de SQL Server

Edita el archivo `.env`:

```
DB_SERVER=192.168.39.150      # IP o nombre del servidor
DB_NAME=NominaInteligente      # Base de datos
DB_USER=sa                     # Usuario
DB_PASSWORD=tu_password        # Contraseña
DB_DRIVER=ODBC Driver 17 for SQL Server
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

> Las dependencias ya están instaladas si ejecutaste el setup inicial.

## Ejecución

Desde la carpeta raíz del proyecto:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Parámetros:**
- `--reload`: Reinicia automáticamente en cambios (desarrollo)
- `--host 0.0.0.0`: Escucha en todas las interfaces de red
- `--port 8000`: Puerto de escucha

### Acceso

- **Local**: http://localhost:8000
- **Red**: http://IP_DEL_SERVIDOR:8000

## Características implementadas

### Dashboard principal (GET `/`)

✅ **Filtros:**
- Fecha (date picker)
- Empresa: TODOS, WYNY, LUXMA, EXTERNO
- Estatus: TODOS, EN_TIEMPO, RETARDO, FALTA_PROBABLE, etc.

✅ **Tarjetas resumen:**
- En tiempo
- Retardos
- Faltas probables
- Descansos
- Permisos
- Vacaciones
- Sin horario
- Pendiente entrada

✅ **Distribución por empresa:**
- Tabla con totales por empresa

✅ **Detalle operativo:**
- Tabla con información de empleados
- Mostrando: número, nombre, departamento, turno, entrada, checadas, retardo, estatus

✅ **Botón "Reprocesar día":**
- POST a `/procesar-dia` (ejecuta `sp_ni_procesar_dia`)

### Vistas/Tablas utilizadas

- `vw_ni_monitor_operativo`: Vista principal de seguimiento
- `vw_ni_resumen_diario_compacto`: Resumen diario compacto
- `ni_jornada_diaria`: Tabla de jornada diaria

## Próximos pasos

1. **Histórico mensual**: Gráficas y rankings de retardos/faltas
2. **Reportes**: Exportación a Excel
3. **Notificaciones**: Alertas en tiempo real
4. **Análisis**: KPIs y métricas avanzadas

## Solución de problemas

### Error de conexión a SQL Server

**Problema**: `pyodbc.OperationalError`

**Soluciones:**
1. Verifica que SQL Server esté corriendo: `SELECT @@VERSION`
2. Verifica las credenciales en `.env`
3. Asegúrate que `ODBC Driver 17 for SQL Server` esté instalado
4. Comprueba firewall (puerto 1433 típicamente)

### Error de vista/tabla no encontrada

**Solución:** Asegúrate que las vistas existan en la BD:

```sql
SELECT * FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME LIKE 'vw_ni%'
```

## Contacto

Desarrollado para NOVA Personal - Sistema de Nómina Inteligente

Prueba de trabajo colaborativo con Git.

Prueba realizada completamente desde Visual Studio Code.

Esta línea se agregó para probar el flujo de Git desde Visual Studio Code.

ESTA NUEVA LINEA ES PARA OTRO CAMBIO NUEVO EN EL ARCHIVO O PARA PROBAR LA RAMA NUEVA

Prueba 2 para ver si se pueden hacer varios cambios 

Nuevos cambios paso 3 y 4

CAmbios en la misma rama w