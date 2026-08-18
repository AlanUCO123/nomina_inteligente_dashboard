from datetime import date, timedelta
import logging
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os

from app.database import fetch_all, fetch_one, execute_sql, _serialize_value
from app.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter()

# Cargar templates
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/health")
def health_check(request: Request):
    """Endpoint para verificar que el servidor está activo"""
    return JSONResponse({
        "status": "ok",
        "host": request.client.host if request.client else "unknown",
        "path": request.url.path
    })

@router.get("/")
def inicio(request: Request):
    """
    Entrada principal de NOVA.

    - Sin sesión -> Login
    - Con sesión -> Dashboard personal
    """
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    return RedirectResponse(url="/home", status_code=303)

@router.get("/monitor", response_class=HTMLResponse)
def dashboard(
    request: Request,
    fecha: str | None = Query(default=None),
    empresa: str = Query(default="WYNY"),
    estatus: str = Query(default="TODOS"),
):
    usuario_id = request.session.get("usuario_id")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    roles_permitidos = {"ADMIN", "SISTEMAS", "RH", "NOMINA"}

    if not any(rol in roles_permitidos for rol in roles):
        return RedirectResponse(url="/home", status_code=303)

    # Obtener datos de sesión
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if fecha is None:
        fecha = date.today().isoformat()

    empresa_filter = ""
    params = {"fecha": fecha}

    if empresa != "TODOS":
        empresa_filter = " AND empresa_origen = :empresa "
        params["empresa"] = empresa

    estatus_filter = ""
    if estatus != "TODOS":
        estatus_filter = " AND estatus_dia = :estatus "
        params["estatus"] = estatus

    resumen = fetch_all(
        f"""
        SELECT
            estatus_dia,
            COUNT(*) AS total
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa = :fecha
        {empresa_filter}
        GROUP BY estatus_dia
        ORDER BY total DESC
        """,
        params,
    )

    tarjetas = {
        "EN_TIEMPO": 0,
        "RETARDO": 0,
        "FALTA_PROBABLE": 0,
        "FALTA_ENTRADA": 0,
        "DESCANSO": 0,
        "PERMISO": 0,
        "VACACIONES": 0,
        "SIN_HORARIO": 0,
        "PENDIENTE_ENTRADA": 0,
        "JORNADA_ANTERIOR": 0,
    }

    for row in resumen:
        tarjetas[row["estatus_dia"]] = row["total"]

    detalle = fetch_all(
        f"""
        SELECT TOP 500
            fecha_operativa,
            empresa_origen,
            numero_empleado,
            nombre_completo,
            departamento,
            origen_horario,
            turno_alias,
            intervalo_alias,
            entrada_esperada,
            salida_esperada,
            primera_checada,
            checada_entrada_valida,
            checada_salida_valida,
            ultima_checada,
            total_checadas,
            minutos_retardo,
            estatus_dia,
            observaciones
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa = :fecha
        {empresa_filter}
        {estatus_filter}
        ORDER BY
            CASE estatus_dia
                WHEN 'FALTA_ENTRADA' THEN 1
                WHEN 'FALTA_PROBABLE' THEN 2
                WHEN 'RETARDO' THEN 3
                WHEN 'PENDIENTE_ENTRADA' THEN 4
                WHEN 'SIN_HORARIO' THEN 5
                WHEN 'EN_TIEMPO' THEN 6
                WHEN 'PERMISO' THEN 7
                WHEN 'VACACIONES' THEN 8
                WHEN 'DESCANSO' THEN 9
                ELSE 10
            END,
            departamento,
            nombre_completo
        """,
        params,
    )

    resumen_empresa = fetch_all(
        """
        SELECT
            empresa_origen,
            COUNT(*) AS total
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa = :fecha
        GROUP BY empresa_origen
        ORDER BY empresa_origen
        """,
        {"fecha": fecha},
    )

    tiempo_extra = fetch_all(
        f"""
        SELECT TOP 500
            fecha_operativa,
            empresa_origen,
            numero_empleado,
            nombre_completo,
            departamento,
            categoria_intelisis,
            tipo_tiempo_extra,
            salida_esperada,
            checada_salida_valida,
            primera_checada,
            ultima_checada,
            minutos_extra_detectados,
            horas_extra_detectadas,
            horas_extra_dobles,
            horas_extra_triples,
            estatus_dia
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa = :fecha
          {empresa_filter}
          AND ISNULL(minutos_extra_detectados, 0) > 0
        ORDER BY minutos_extra_detectados DESC
        """,
        params,
    )

    resumen_he = fetch_one(
        f"""
        SELECT
            CAST(SUM(ISNULL(minutos_extra_detectados, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
            CAST(SUM(ISNULL(minutos_extra_dobles, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_dobles,
            CAST(SUM(ISNULL(minutos_extra_triples, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_triples,
            COUNT(CASE WHEN ISNULL(minutos_extra_detectados, 0) > 0 THEN 1 END) AS personas_he
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa = :fecha
          {empresa_filter}
        """,
        params,
    ) or {"horas_detectadas": 0, "horas_dobles": 0, "horas_triples": 0, "personas_he": 0}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "fecha": fecha,
            "empresa": empresa,
            "estatus": estatus,
            "tarjetas": tarjetas,
            "resumen": resumen,
            "detalle": detalle,
            "resumen_empresa": resumen_empresa,
            "tiempo_extra": tiempo_extra,
            "resumen_he": resumen_he,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        },
    )

@router.post("/procesar-dia")
def procesar_dia(
    request: Request,
    fecha: str = Query(...)
):
    usuario_id = request.session.get("usuario_id")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    roles_permitidos = {"ADMIN", "SISTEMAS", "RH", "NOMINA"}

    if not any(rol in roles_permitidos for rol in roles):
        return RedirectResponse(url="/home", status_code=303)

    execute_sql(
        "EXEC sp_ni_procesar_dia @fecha = :fecha",
        {"fecha": fecha},
    )

    return RedirectResponse(
        url=f"/monitor?fecha={fecha}&empresa=WYNY",
        status_code=303
    )

@router.get("/historico", response_class=HTMLResponse)
def historico(
    request: Request,
    fecha_inicio: str = Query(default="2026-06-01"),
    fecha_fin: str | None = Query(default=None),
    empresa: str = Query(default="WYNY"),
):
    # Obtener datos de sesión
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    if fecha_fin is None:
        fecha_fin = date.today().isoformat()

    empresa_filter = ""
    params = {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    }

    if empresa != "TODOS":
        empresa_filter = " AND empresa_origen = :empresa "
        params["empresa"] = empresa

    # Resumen por día
    resumen = fetch_all(
        f"""
        SELECT
            fecha_operativa,
            empresa_origen,
            SUM(CASE WHEN estatus_dia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_dia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 ELSE 0 END) AS falta_entrada,
            SUM(CASE WHEN estatus_dia = 'FALTA_PROBABLE' THEN 1 ELSE 0 END) AS faltas_probables,
            SUM(CASE WHEN estatus_dia = 'DESCANSO' THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN estatus_dia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(CASE WHEN estatus_dia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_dia = 'SIN_HORARIO' THEN 1 ELSE 0 END) AS sin_horario,
            COUNT(*) AS total
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa >= :fecha_inicio
          AND fecha_operativa <= :fecha_fin
          {empresa_filter}
        GROUP BY fecha_operativa, empresa_origen
        ORDER BY fecha_operativa DESC, empresa_origen
        """,
        params,
    )

    # Totales por empresa del período
    totales = fetch_all(
        f"""
        SELECT
            empresa_origen,
            SUM(CASE WHEN estatus_dia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_dia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 ELSE 0 END) AS falta_entrada,
            SUM(CASE WHEN estatus_dia = 'FALTA_PROBABLE' THEN 1 ELSE 0 END) AS faltas_probables,
            SUM(CASE WHEN estatus_dia = 'DESCANSO' THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN estatus_dia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(CASE WHEN estatus_dia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_dia = 'SIN_HORARIO' THEN 1 ELSE 0 END) AS sin_horario,
            COUNT(*) AS total
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa >= :fecha_inicio
          AND fecha_operativa <= :fecha_fin
          {empresa_filter}
        GROUP BY empresa_origen
        ORDER BY empresa_origen
        """,
        params,
    )

    # Top retardos
    top_retardos = fetch_all(
        f"""
        SELECT TOP 10
            numero_empleado,
            nombre_completo,
            departamento,
            COUNT(CASE WHEN estatus_dia = 'RETARDO' THEN 1 END) AS dias_con_retardo,
            ISNULL(SUM(CASE WHEN estatus_dia = 'RETARDO' THEN minutos_retardo ELSE 0 END), 0) AS minutos_retardo_total
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa >= :fecha_inicio
          AND fecha_operativa <= :fecha_fin
          {empresa_filter}
        GROUP BY numero_empleado, nombre_completo, departamento
        HAVING COUNT(CASE WHEN estatus_dia = 'RETARDO' THEN 1 END) > 0
        ORDER BY minutos_retardo_total DESC
        """,
        params,
    )

    # Top falta de entrada
    top_falta_entrada = fetch_all(
        f"""
        SELECT TOP 10
            numero_empleado,
            nombre_completo,
            departamento,
            COUNT(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 END) AS dias_sin_entrada
        FROM vw_ni_monitor_operativo
        WHERE fecha_operativa >= :fecha_inicio
          AND fecha_operativa <= :fecha_fin
          {empresa_filter}
        GROUP BY numero_empleado, nombre_completo, departamento
        HAVING COUNT(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 END) > 0
        ORDER BY dias_sin_entrada DESC
        """,
        params,
    )

    return templates.TemplateResponse(
        request=request,
        name="historico.html",
        context={
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "empresa": empresa,
            "resumen": resumen,
            "totales": totales if totales else {},
            "top_retardos": top_retardos,
            "top_falta_entrada": top_falta_entrada,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        },
    )

@router.get("/precierre", response_class=HTMLResponse)
def precierre(
    request: Request,
    fecha_inicio: str = Query(default="2026-06-10"),
    empresa: str = Query(default="WYNY"),
    departamento: str = Query(default="TODOS"),
):
    # Obtener datos de sesión
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    inicio = date.fromisoformat(fecha_inicio)
    fin = inicio + timedelta(days=6)

    empresa_filter = ""
    departamento_filter = ""

    params = {
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
    }

    if empresa != "TODOS":
        empresa_filter = " AND empresa_origen = :empresa "
        params["empresa"] = empresa

    if departamento != "TODOS":
        departamento_filter = " AND departamento = :departamento "
        params["departamento"] = departamento

    resumen_general = fetch_one(
        f"""
        SELECT
            COUNT(DISTINCT numero_empleado) AS empleados,
            SUM(CASE WHEN estatus_dia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS asistencias,
            SUM(CASE WHEN estatus_dia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 ELSE 0 END) AS faltas_entrada,
            SUM(CASE WHEN estatus_dia = 'FALTA_PROBABLE' THEN 1 ELSE 0 END) AS faltas_probables,
            SUM(CASE WHEN estatus_dia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(CASE WHEN estatus_dia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_dia = 'DESCANSO' THEN 1 ELSE 0 END) AS descansos,
            CAST(SUM(ISNULL(minutos_extra_dobles, 0)) / 60.0 AS DECIMAL(10,2)) AS he_dobles,
            CAST(SUM(ISNULL(minutos_extra_triples, 0)) / 60.0 AS DECIMAL(10,2)) AS he_triples
        FROM vw_ni_precierre_prenomina
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {empresa_filter}
          {departamento_filter}
        """,
        params,
    )

    resumen_departamento = fetch_all(
        f"""
        SELECT
            departamento,
            COUNT(DISTINCT numero_empleado) AS empleados,
            SUM(CASE WHEN estatus_dia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS asistencias,
            SUM(CASE WHEN estatus_dia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 ELSE 0 END) AS faltas_entrada,
            SUM(CASE WHEN estatus_dia = 'FALTA_PROBABLE' THEN 1 ELSE 0 END) AS faltas_probables,
            SUM(CASE WHEN estatus_dia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(CASE WHEN estatus_dia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            CAST(SUM(ISNULL(minutos_extra_dobles, 0)) / 60.0 AS DECIMAL(10,2)) AS he_dobles,
            CAST(SUM(ISNULL(minutos_extra_triples, 0)) / 60.0 AS DECIMAL(10,2)) AS he_triples
        FROM vw_ni_precierre_prenomina
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {empresa_filter}
          {departamento_filter}
        GROUP BY departamento
        ORDER BY departamento
        """,
        params,
    )

    departamentos = fetch_all(
        f"""
        SELECT DISTINCT departamento
        FROM vw_ni_precierre_prenomina
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {empresa_filter}
        ORDER BY departamento
        """,
        params,
    )

    detalle = fetch_all(
        f"""
        SELECT
            departamento,
            numero_empleado,
            nombre_completo,

            MAX(CASE WHEN fecha_operativa = :fecha_inicio THEN codigo_dia END) AS dia_1,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 1, :fecha_inicio) THEN codigo_dia END) AS dia_2,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 2, :fecha_inicio) THEN codigo_dia END) AS dia_3,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 3, :fecha_inicio) THEN codigo_dia END) AS dia_4,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 4, :fecha_inicio) THEN codigo_dia END) AS dia_5,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 5, :fecha_inicio) THEN codigo_dia END) AS dia_6,
            MAX(CASE WHEN fecha_operativa = DATEADD(DAY, 6, :fecha_inicio) THEN codigo_dia END) AS dia_7,

            SUM(CASE WHEN estatus_dia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS asistencias,
            SUM(CASE WHEN estatus_dia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_dia = 'FALTA_ENTRADA' THEN 1 ELSE 0 END) AS faltas_entrada,
            SUM(CASE WHEN estatus_dia = 'FALTA_PROBABLE' THEN 1 ELSE 0 END) AS faltas_probables,
            SUM(CASE WHEN estatus_dia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(CASE WHEN estatus_dia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,

            CAST(SUM(ISNULL(minutos_extra_dobles, 0)) / 60.0 AS DECIMAL(10,2)) AS he_dobles,
            CAST(SUM(ISNULL(minutos_extra_triples, 0)) / 60.0 AS DECIMAL(10,2)) AS he_triples,
            SUM(ISNULL(minutos_retardo, 0)) AS minutos_retardo_total
        FROM vw_ni_precierre_prenomina
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {empresa_filter}
          {departamento_filter}
        GROUP BY departamento, numero_empleado, nombre_completo
        ORDER BY departamento, nombre_completo
        """,
        params,
    )

    fechas = [
        inicio,
        inicio + timedelta(days=1),
        inicio + timedelta(days=2),
        inicio + timedelta(days=3),
        inicio + timedelta(days=4),
        inicio + timedelta(days=5),
        inicio + timedelta(days=6),
    ]

    return templates.TemplateResponse(
        request=request,
        name="precierre.html",
        context={
            "fecha_inicio": inicio.isoformat(),
            "fecha_fin": fin.isoformat(),
            "empresa": empresa,
            "departamento": departamento,
            "departamentos": departamentos,
            "resumen_general": resumen_general,
            "resumen_departamento": resumen_departamento,
            "detalle": detalle,
            "fechas": fechas,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        },
    )

@router.get("/alertas", response_class=HTMLResponse)
def alertas(
    request: Request,
    fecha: str = Query(default="2026-06-11"),
    estatus: str = Query(default="PENDIENTE"),
    tipo: str = Query(default="TODOS"),
):
    # Obtener datos de sesión
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    params = {
        "fecha": fecha,
        "estatus": estatus,
    }

    tipo_filter = ""
    if tipo != "TODOS":
        tipo_filter = " AND tipo_alerta = :tipo "
        params["tipo"] = tipo

    registros = fetch_all(
        f"""
        SELECT TOP 500
            id,
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            tipo_alerta,
            destinatario_tipo,
            telefono_destino,
            mensaje,
            estatus,
            intentos,
            fecha_creacion,
            fecha_envio,
            error_envio
        FROM ni_alertas_whatsapp
        WHERE fecha_operativa = :fecha
          AND estatus = :estatus
          {tipo_filter}
        ORDER BY fecha_creacion DESC
        """,
        params,
    )

    return templates.TemplateResponse(
        request=request,
        name="alertas.html",
        context={
            "fecha": fecha,
            "estatus": estatus,
            "tipo": tipo,
            "registros": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in registros
            ],
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        },
    )

@router.post("/enviar-alerta/{alerta_id}")
def enviar_alerta(alerta_id: int):
    """
    Envía una alerta específica a través de WhatsApp.
    """
    try:
        # Obtener datos de la alerta
        alerta = fetch_one(
            """
            SELECT
                id,
                numero_empleado,
                nombre_completo,
                tipo_alerta,
                telefono_destino,
                mensaje,
                estatus,
                fecha_operativa
            FROM ni_alertas_whatsapp
            WHERE id = :id
            """,
            {"id": alerta_id}
        )
        
        if not alerta:
            return JSONResponse(
                status_code=404,
                content={"error": "Alerta no encontrada"}
            )
        
        if alerta["estatus"] != "PENDIENTE":
            return JSONResponse(
                status_code=400,
                content={"error": f"La alerta ya fue enviada (estatus: {alerta['estatus']})"}
            )
        
        # Determinar la hora actual
        from datetime import datetime
        hora_actual = datetime.now().strftime("%H:%M:%S")
        
        # Enviar a través de WhatsApp
        resultado = WhatsAppService.enviar_alerta(
            telefono=alerta["telefono_destino"],
            nombre_empleado=alerta["nombre_completo"],
            tipo_alerta=alerta["tipo_alerta"],
            fecha=alerta["fecha_operativa"],
            hora=hora_actual,
            valor=alerta["mensaje"],
            numero_empleado=alerta["numero_empleado"]
        )
        
        # Actualizar estado en BD
        if resultado["success"]:
            execute_sql(
                """
                UPDATE ni_alertas_whatsapp
                SET estatus = 'ENVIADO', 
                    fecha_envio = GETDATE(),
                    intentos = intentos + 1
                WHERE id = :id
                """,
                {"id": alerta_id}
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Alerta enviada correctamente",
                    "alerta_id": alerta_id,
                    "telefono": alerta["telefono_destino"],
                    "tipo": alerta["tipo_alerta"]
                }
            )
        else:
            # Registrar error
            execute_sql(
                """
                UPDATE ni_alertas_whatsapp
                SET estatus = 'ERROR',
                    error_envio = :error,
                    intentos = intentos + 1
                WHERE id = :id
                """,
                {
                    "id": alerta_id,
                    "error": resultado.get("error", "Error desconocido")
                }
            )
            
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Error al enviar alerta",
                    "error": resultado.get("error"),
                    "alerta_id": alerta_id
                }
            )
    
    except Exception as e:
        logger.error(f"Error al enviar alerta {alerta_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.post("/enviar-alertas-pendientes")
def enviar_alertas_pendientes(fecha: str = Query(...)):
    """
    Envía todas las alertas pendientes de una fecha específica.
    """
    try:
        # Obtener todas las alertas pendientes de la fecha
        alertas = fetch_all(
            """
            SELECT
                id,
                numero_empleado,
                nombre_completo,
                tipo_alerta,
                telefono_destino,
                mensaje,
                estatus,
                fecha_operativa
            FROM ni_alertas_whatsapp
            WHERE fecha_operativa = :fecha
              AND estatus = 'PENDIENTE'
            ORDER BY fecha_creacion ASC
            """,
            {"fecha": fecha}
        )
        
        from datetime import datetime
        hora_actual = datetime.now().strftime("%H:%M:%S")
        
        resultados = {
            "total": len(alertas),
            "exitosas": 0,
            "fallidas": 0,
            "detalles": []
        }
        
        for alerta in alertas:
            resultado = WhatsAppService.enviar_alerta(
                telefono=alerta["telefono_destino"],
                nombre_empleado=alerta["nombre_completo"],
                tipo_alerta=alerta["tipo_alerta"],
                fecha=alerta["fecha_operativa"],
                hora=hora_actual,
                valor=alerta["mensaje"],
                numero_empleado=alerta["numero_empleado"]
            )
            
            if resultado["success"]:
                execute_sql(
                    """
                    UPDATE ni_alertas_whatsapp
                    SET estatus = 'ENVIADO',
                        fecha_envio = GETDATE(),
                        intentos = intentos + 1
                    WHERE id = :id
                    """,
                    {"id": alerta["id"]}
                )
                resultados["exitosas"] += 1
                resultados["detalles"].append({
                    "alerta_id": alerta["id"],
                    "empleado": alerta["nombre_completo"],
                    "tipo": alerta["tipo_alerta"],
                    "estado": "ENVIADO"
                })
            else:
                execute_sql(
                    """
                    UPDATE ni_alertas_whatsapp
                    SET estatus = 'ERROR',
                        error_envio = :error,
                        intentos = intentos + 1
                    WHERE id = :id
                    """,
                    {
                        "id": alerta["id"],
                        "error": resultado.get("error", "Error desconocido")
                    }
                )
                resultados["fallidas"] += 1
                resultados["detalles"].append({
                    "alerta_id": alerta["id"],
                    "empleado": alerta["nombre_completo"],
                    "tipo": alerta["tipo_alerta"],
                    "estado": "ERROR",
                    "error": resultado.get("error")
                })
        
        return JSONResponse(
            status_code=200,
            content=resultados
        )
    
    except Exception as e:
        logger.error(f"Error al enviar alertas pendientes: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.get("/whatsapp-health")
def whatsapp_health():
    """
    Verifica el estado de la API de WhatsApp.
    """
    try:
        is_healthy = WhatsAppService.verificar_salud()
        
        if is_healthy:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "message": "API de WhatsApp está operativa"
                }
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "API de WhatsApp no está disponible"
                }
            )
    except Exception as e:
        logger.error(f"Error al verificar salud de WhatsApp: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": str(e)
            }
        )
