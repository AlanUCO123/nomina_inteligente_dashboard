from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import text
from app.database import engine
import os
import smtplib
from datetime import date, timedelta
from email.mime.text import MIMEText

router = APIRouter()

# Templates se obtiene de app.main
templates = None

def set_templates(tmpl):
    global templates
    templates = tmpl

# Funciones de validación de permisos
def usuario_es_admin(roles: list[str]) -> bool:
    """Verifica si el usuario tiene roles administrativos."""
    return any(rol in roles for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"])

def validar_permiso_evento_he(
    evento_id: int,
    numero_empleado_sesion: str | None,
    roles: list[str]
) -> bool:
    """
    ADMIN/SISTEMAS/RH/NOMINA:
        pueden modificar cualquier evento.

    GERENTE:
        puede modificar eventos de empleados de su gerencia.

    SUPERVISOR:
        puede modificar eventos de empleados que le reportan.
    """

    if usuario_es_admin(roles):
        return True

    if not numero_empleado_sesion:
        return False

    sql = text("""
        SELECT TOP 1
            id,
            supervisor_numero,
            gerente_numero
        FROM dbo.ni_he_eventos_jornada
        WHERE id = :evento_id
    """)

    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {"evento_id": evento_id}
        ).mappings().first()

    if not row:
        return False

    # El rol más alto tiene prioridad.
    if "GERENTE" in roles:
        return (
            str(row["gerente_numero"] or "")
            == str(numero_empleado_sesion)
        )

    if "SUPERVISOR" in roles:
        return (
            str(row["supervisor_numero"] or "")
            == str(numero_empleado_sesion)
        )

    return False


def validar_permiso_empleado_he(
    numero_empleado_objetivo: str,
    numero_empleado_sesion: str | None,
    roles: list[str]
) -> bool:
    """
    ADMIN/SISTEMAS/RH/NOMINA:
        pueden agregar HE a cualquier empleado.

    GERENTE:
        puede agregar HE a empleados de su gerencia.

    SUPERVISOR:
        puede agregar HE únicamente a empleados que le reportan.
    """

    if usuario_es_admin(roles):
        return True

    if not numero_empleado_sesion:
        return False

    sql = text("""
        SELECT TOP 1
            numero_empleado,
            reporta_a,
            gerente
        FROM dbo.ni_empleados_maestro
        WHERE numero_empleado = :numero_empleado
    """)

    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {"numero_empleado": numero_empleado_objetivo}
        ).mappings().first()

    if not row:
        return False

    # GERENTE tiene prioridad sobre SUPERVISOR.
    if "GERENTE" in roles:
        return (
            str(row["gerente"] or "")
            == str(numero_empleado_sesion)
        )

    if "SUPERVISOR" in roles:
        return (
            str(row["reporta_a"] or "")
            == str(numero_empleado_sesion)
        )

    return False

def obtener_periodo_miercoles_martes():
    """
    Regresa el periodo actual de miércoles a martes.
    """
    hoy = date.today()

    # Python:
    # lunes=0, martes=1, miércoles=2...
    dias_desde_miercoles = (hoy.weekday() - 2) % 7

    fecha_inicio = hoy - timedelta(days=dias_desde_miercoles)
    fecha_fin = fecha_inicio + timedelta(days=6)

    return fecha_inicio.isoformat(), fecha_fin.isoformat()

@router.get("/he-control")
def he_control(
    request: Request,
    token: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    departamento: str | None = None,
    estatus: str = "TODOS",
    supervisor_numero: str | None = None,
    gerente_numero: str | None = None,
):
    # Leer datos de sesión
    usuario_id = request.session.get("usuario_id")
    semana_piloto = None
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Validar acceso: debe tener sesión O token
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Aplicar alcance por rol cuando está autenticado
    es_admin = usuario_es_admin(roles)
    
    if not token:
        if not es_admin:

            # DIRECTOR todavía no participa en el flujo de autorización HE.
            # Debe bloquearse antes de evaluar GERENTE/SUPERVISOR,
            # porque los roles son acumulativos.
            if "DIRECTOR" in roles:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "mensaje": "El perfil DIRECTOR no tiene habilitado el Control HE."
                })

            # GERENTE tiene prioridad sobre SUPERVISOR
            elif "GERENTE" in roles:
                gerente_numero = numero_empleado_sesion
                supervisor_numero = None

            elif "SUPERVISOR" in roles:
                supervisor_numero = numero_empleado_sesion
                gerente_numero = None

            else:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "mensaje": "No tienes permiso para acceder al Control HE."
                })
    
    # Si viene token, validar y cargar datos desde ni_he_tokens_revision
    if token:
        try:
            token_sql = text("""
                SELECT
                    fecha_inicio,
                    fecha_fin,
                    semana_piloto,
                    supervisor_numero,
                    departamento,
                    rol_acceso
                FROM ni_he_tokens_revision
                WHERE token = :token
                  AND activo = 1
                  AND (fecha_expiracion IS NULL OR fecha_expiracion >= GETDATE())
            """)
            
            with engine.connect() as conn:
                token_info = conn.execute(token_sql, {"token": token}).mappings().first()
                
                if not token_info:
                    return templates.TemplateResponse("error.html", {
                        "request": request,
                        "mensaje": "La liga de revisión no es válida o ya expiró."
                    })
                
                # Registrar acceso en la tabla
                update_access_sql = text("""
                    UPDATE ni_he_tokens_revision
                    SET ultimo_acceso = GETDATE()
                    WHERE token = :token
                """)
                
                conn.execute(update_access_sql, {"token": token})
                conn.commit()
            
            # Cargar datos exclusivamente desde el token
            fecha_inicio = str(token_info["fecha_inicio"])
            fecha_fin = str(token_info["fecha_fin"])
            semana_piloto = token_info["semana_piloto"]

            supervisor_numero = token_info["supervisor_numero"]

            # Los tokens actuales pertenecen a supervisores,
            # por lo que nunca deben heredar un filtro de gerente
            # enviado manualmente por la URL.
            gerente_numero = None

            departamento = token_info["departamento"] or "TODOS"
        except Exception as e:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": f"Error al validar la liga de revisión. Verifique con el administrador."
            })
    
    # Valores por defecto si no vienen de token
    # Periodo por defecto: miércoles -> martes actual
    if not fecha_inicio or not fecha_fin:
        periodo_inicio, periodo_fin = obtener_periodo_miercoles_martes()

        fecha_inicio = fecha_inicio or periodo_inicio
        fecha_fin = fecha_fin or periodo_fin

    departamento = (departamento or "TODOS").strip().upper()
    estatus = (estatus or "TODOS").strip().upper()
    
    sql = text("""
        SELECT
            e.evento_base_id AS id,
            e.fecha_operativa,
            e.numero_empleado,
            e.nombre_completo,
            e.departamento,
            e.tipo_he,
            e.salida_esperada,
            e.checada_salida_valida,
            e.ultima_checada,
            e.minutos_base,
            e.minutos_ajuste_total,
            e.minutos_finales,
            e.horas_base AS horas_detectadas,
            e.horas_ajuste,
            e.horas_finales AS horas_autorizadas,
            e.estatus,
            e.supervisor_numero,
            e.supervisor_nombre,
            e.gerente_numero,
            e.gerente_nombre,
            e.semana_piloto,
            e.origen,
            e.total_ajustes
        FROM vw_ni_he_eventos_resumen e
        WHERE e.fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
        AND e.semana_piloto = '2026-06-24_2026-06-30'
        AND (
                :supervisor_numero IS NULL
                OR e.supervisor_numero = :supervisor_numero
            )
        AND (
                :gerente_numero IS NULL
                OR e.gerente_numero = :gerente_numero
            )
        AND (:departamento = 'TODOS' OR e.departamento = :departamento)
        AND (:estatus = 'TODOS' OR e.estatus = :estatus)
        ORDER BY
            e.fecha_operativa,
            e.departamento,
            e.nombre_completo
    """)

    kpi_sql = text("""
        SELECT
            COUNT(*) AS total_eventos,
            COUNT(DISTINCT numero_empleado) AS empleados,
            SUM(CASE WHEN estatus = 'PENDIENTE' THEN 1 ELSE 0 END) AS pendientes,
            SUM(CASE WHEN estatus IN ('CONFIRMADA','AJUSTADA') THEN 1 ELSE 0 END) AS confirmadas,
            SUM(CASE WHEN estatus = 'RECHAZADA' THEN 1 ELSE 0 END) AS rechazadas,
            CAST(SUM(ISNULL(minutos_base, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
            CAST(SUM(ISNULL(minutos_ajuste_total, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_ajuste,
            CAST(SUM(ISNULL(minutos_finales, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas
        FROM vw_ni_he_eventos_resumen
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
        AND semana_piloto = '2026-06-24_2026-06-30'
        AND (
                :supervisor_numero IS NULL
                OR supervisor_numero = :supervisor_numero
            )
        AND (
                :gerente_numero IS NULL
                OR gerente_numero = :gerente_numero
            )
        AND (:departamento = 'TODOS' OR departamento = :departamento)
        AND (:estatus = 'TODOS' OR estatus = :estatus)
    """)

    params = {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "semana_piloto": semana_piloto,
        "departamento": departamento,
        "estatus": estatus,
        "supervisor_numero": supervisor_numero,
        "gerente_numero": gerente_numero,
    }

    departamentos_sql = text("""
        SELECT DISTINCT
            LTRIM(RTRIM(departamento)) AS departamento
        FROM ni_he_eventos_jornada
        WHERE semana_piloto = '2026-06-24_2026-06-30'
        AND fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
        AND departamento IS NOT NULL
        AND LTRIM(RTRIM(departamento)) <> ''
        ORDER BY departamento
    """)

    with engine.begin() as conn:
        eventos = conn.execute(sql, params).mappings().all()
        kpis = conn.execute(kpi_sql, params).mappings().first()
        departamentos = conn.execute(departamentos_sql, params).scalars().all()

    return templates.TemplateResponse("he_control.html", {
        "request": request,
        "eventos": eventos,
        "kpis": kpis,
        "departamentos": departamentos,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "departamento": departamento,
        "estatus": estatus,
        "supervisor_numero": supervisor_numero,
        "token": token,
        "login_user": login_user,
        "nombre_usuario": request.session.get("nombre_usuario"),
        "numero_empleado": numero_empleado_sesion,
        "roles": roles,
        "usuario_actual": {
            "login_user": login_user,
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
            "es_admin": es_admin,
        } if usuario_id else None,
    })


@router.post("/he-control/confirmar")
def confirmar_he(
    request: Request,
    evento_id: int = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str = Form("TODOS"),
    estatus: str = Form("TODOS"),
    token: str | None = Form(None),
):
    # Validar sesión
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Si no hay sesión ni token, redirigir a login
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Validar permiso solo si accede con sesión (no token)
    if not token:
        if not validar_permiso_evento_he(evento_id, numero_empleado_sesion, roles):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": "No tienes permiso para confirmar este evento de tiempo extra."
            })
    
    usuario_accion = login_user or "TOKEN"
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_evento_confirmar
                    @evento_id = :evento_id,
                    @usuario = :usuario,
                    @comentario = :comentario
            """),
            {
                "evento_id": evento_id,
                "usuario": usuario_accion,
                "comentario": "Confirmado desde Control HE"
            }
        )

    extra = f"&token={token}" if token else ""
    return RedirectResponse(
        f"/he-control?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}&departamento={departamento}&estatus={estatus}{extra}",
        status_code=303
    )


@router.post("/he-control/rechazar")
def rechazar_he(
    request: Request,
    evento_id: int = Form(...),
    motivo: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str = Form("TODOS"),
    estatus: str = Form("TODOS"),
    token: str | None = Form(None),
):
    # Validar sesión
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Si no hay sesión ni token, redirigir a login
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Validar permiso solo si accede con sesión (no token)
    if not token:
        if not validar_permiso_evento_he(evento_id, numero_empleado_sesion, roles):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": "No tienes permiso para rechazar este evento de tiempo extra."
            })
    
    usuario_accion = login_user or "TOKEN"
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_evento_rechazar
                    @evento_id = :evento_id,
                    @motivo = :motivo,
                    @usuario = :usuario
            """),
            {
                "evento_id": evento_id,
                "motivo": motivo,
                "usuario": usuario_accion
            }
        )

    extra = f"&token={token}" if token else ""
    return RedirectResponse(
        f"/he-control?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}&departamento={departamento}&estatus={estatus}{extra}",
        status_code=303
    )


@router.post("/he-control/ajustar")
def ajustar_he(
    request: Request,
    evento_id: int = Form(...),
    minutos_autorizados: int = Form(...),
    motivo: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str = Form("TODOS"),
    estatus: str = Form("TODOS"),
    token: str | None = Form(None),
):
    # Validar sesión
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Si no hay sesión ni token, redirigir a login
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Validar permiso solo si accede con sesión (no token)
    if not token:
        if not validar_permiso_evento_he(evento_id, numero_empleado_sesion, roles):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": "No tienes permiso para ajustar este evento de tiempo extra."
            })
    
    usuario_accion = login_user or "TOKEN"
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_evento_ajustar
                    @evento_id = :evento_id,
                    @minutos_autorizados = :minutos_autorizados,
                    @motivo = :motivo,
                    @usuario = :usuario
            """),
            {
                "evento_id": evento_id,
                "minutos_autorizados": minutos_autorizados,
                "motivo": motivo,
                "usuario": usuario_accion
            }
        )

    extra = f"&token={token}" if token else ""
    return RedirectResponse(
        f"/he-control?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}&departamento={departamento}&estatus={estatus}{extra}",
        status_code=303
    )


@router.post("/he-control/agregar-manual")
def agregar_he_manual(
    request: Request,
    fecha_operativa: str = Form(...),
    numero_empleado: str = Form(...),
    tipo_he: str = Form(...),
    horas_autorizadas: float = Form(...),
    tipo_evidencia: str = Form(...),
    motivo: str = Form(...),
    hora_inicio_reportada: str | None = Form(None),
    hora_fin_reportada: str | None = Form(None),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento_filtro: str = Form("TODOS"),
    estatus_filtro: str = Form("TODOS"),
    token: str | None = Form(None),
):
    from datetime import datetime
    
    # Validar sesión
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Si no hay sesión ni token, redirigir a login
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Validar permiso solo si accede con sesión (no token)
    if not token:
        if not validar_permiso_empleado_he(numero_empleado, numero_empleado_sesion, roles):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": "No tienes permiso para agregar HE manual a este empleado."
            })
    
    usuario_accion = login_user or "TOKEN"
    minutos_autorizados = int(round(horas_autorizadas * 60))
    
    # Convertir datetime-local format (ISO) a datetime objects
    hora_inicio = None
    hora_fin = None
    
    if hora_inicio_reportada:
        try:
            hora_inicio = datetime.fromisoformat(hora_inicio_reportada)
        except:
            hora_inicio = None
    
    if hora_fin_reportada:
        try:
            hora_fin = datetime.fromisoformat(hora_fin_reportada)
        except:
            hora_fin = None
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_agregar_manual
                    @fecha_operativa = :fecha_operativa,
                    @numero_empleado = :numero_empleado,
                    @tipo_he = :tipo_he,
                    @minutos_autorizados = :minutos_autorizados,
                    @hora_inicio_reportada = :hora_inicio_reportada,
                    @hora_fin_reportada = :hora_fin_reportada,
                    @tipo_evidencia = :tipo_evidencia,
                    @motivo = :motivo,
                    @usuario = :usuario,
                    @semana_piloto = :semana_piloto
            """),
            {
                "fecha_operativa": fecha_operativa,
                "numero_empleado": numero_empleado,
                "tipo_he": tipo_he,
                "minutos_autorizados": minutos_autorizados,
                "hora_inicio_reportada": hora_inicio,
                "hora_fin_reportada": hora_fin,
                "tipo_evidencia": tipo_evidencia,
                "motivo": motivo,
                "usuario": usuario_accion,
                "semana_piloto": f"{fecha_inicio}_{fecha_fin}",
            }
        )
    
    extra = f"&token={token}" if token else ""
    return RedirectResponse(
        f"/he-control?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}&departamento={departamento_filtro}&estatus={estatus_filtro}{extra}",
        status_code=303
    )


@router.post("/he-control/agregar-ajuste")
def agregar_ajuste_he(
    request: Request,
    evento_base_id: int = Form(...),
    tipo_ajuste: str = Form(...),
    horas_ajuste: float = Form(...),
    tipo_evidencia: str = Form(...),
    motivo: str = Form(...),
    hora_inicio_reportada: str | None = Form(None),
    hora_fin_reportada: str | None = Form(None),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento_filtro: str = Form("TODOS"),
    estatus_filtro: str = Form("TODOS"),
    token: str | None = Form(None),
):
    from datetime import datetime
    
    # Validar sesión
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])
    
    # Si no hay sesión ni token, redirigir a login
    if not usuario_id and not token:
        return RedirectResponse(url="/login", status_code=303)
    
    # Validar permiso solo si accede con sesión (no token)
    if not token:
        if not validar_permiso_evento_he(evento_base_id, numero_empleado_sesion, roles):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "mensaje": "No tienes permiso para ajustar este evento de tiempo extra."
            })
    
    usuario_accion = login_user or "TOKEN"
    
    # Convertir datetime-local format (ISO) a datetime objects
    hora_inicio = None
    hora_fin = None
    
    if hora_inicio_reportada:
        try:
            hora_inicio = datetime.fromisoformat(hora_inicio_reportada)
        except:
            hora_inicio = None
    
    if hora_fin_reportada:
        try:
            hora_fin = datetime.fromisoformat(hora_fin_reportada)
        except:
            hora_fin = None
    
    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_evento_agregar_ajuste
                    @evento_base_id = :evento_base_id,
                    @tipo_ajuste = :tipo_ajuste,
                    @horas_ajuste = :horas_ajuste,
                    @tipo_evidencia = :tipo_evidencia,
                    @motivo = :motivo,
                    @hora_inicio_reportada = :hora_inicio_reportada,
                    @hora_fin_reportada = :hora_fin_reportada,
                    @usuario = :usuario
            """),
            {
                "evento_base_id": evento_base_id,
                "tipo_ajuste": tipo_ajuste,
                "horas_ajuste": horas_ajuste,
                "tipo_evidencia": tipo_evidencia,
                "motivo": motivo,
                "hora_inicio_reportada": hora_inicio,
                "hora_fin_reportada": hora_fin,
                "usuario": usuario_accion,
            }
        )
    
    extra = f"&token={token}" if token else ""
    return RedirectResponse(
        url=f"/he-control?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}&departamento={departamento_filtro}&estatus={estatus_filtro}{extra}",
        status_code=303
    )


@router.post("/he-control/enviar-notificacion-prueba")
def enviar_notificacion_prueba():
    """
    Ruta temporal para enviar notificaciones por email.
    Busca la notificación PENDIENTE más reciente y la envía.
    
    Configurar variables de entorno:
    - SMTP_SERVER: Servidor SMTP (ej: smtp.gmail.com)
    - SMTP_PORT: Puerto SMTP (ej: 587)
    - SMTP_USER: Usuario para autenticación
    - SMTP_PASSWORD: Contraseña para autenticación
    - SMTP_FROM: Email remitente (ej: nova@wyny.mx)
    """
    
    # Obtener configuración desde variables de entorno
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))  # Puerto 587 sin TLS
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "nova@wyny.mx")
    
    if not smtp_user or not smtp_password:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "mensaje": "Credenciales SMTP no configuradas"}
        )
    
    try:
        with engine.begin() as conn:
            # Obtener notificación pendiente más reciente
            n = conn.execute(
                text("""
                    SELECT TOP 1
                        id,
                        destino,
                        asunto,
                        mensaje,
                        supervisor_nombre,
                        supervisor_numero,
                        departamento,
                        eventos_pendientes
                    FROM ni_he_notificaciones_revision
                    WHERE estatus = 'PENDIENTE'
                    ORDER BY id DESC
                """)
            ).mappings().first()
            
            if not n:
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "mensaje": "No hay notificaciones pendientes"}
                )
            
            # Obtener o generar token para el supervisor
            token = conn.execute(
                text("""
                    SELECT TOP 1 token
                    FROM ni_he_tokens_revision
                    WHERE supervisor_numero = :supervisor_numero
                        AND activo = 1
                        AND fecha_expiracion >= GETDATE()
                    ORDER BY fecha_creacion DESC
                """),
                {"supervisor_numero": n["supervisor_numero"]}
            ).scalar()
            
            # Si no existe token válido, generar uno nuevo
            if not token:
                import secrets
                token = secrets.token_hex(16)
                conn.execute(
                    text("""
                        INSERT INTO ni_he_tokens_revision (
                            token, supervisor_numero, supervisor_nombre, departamento,
                            activo, fecha_creacion, fecha_expiracion
                        ) VALUES (
                            :token, :supervisor_numero, :supervisor_nombre, :departamento,
                            1, GETDATE(), DATEADD(day, 7, GETDATE())
                        )
                    """),
                    {
                        "token": token,
                        "supervisor_numero": n["supervisor_numero"],
                        "supervisor_nombre": n["supervisor_nombre"],
                        "departamento": n["departamento"]
                    }
                )
            
            # Construir URL del panel
            panel_url = f"http://192.168.39.122:8009/he-control?token={token}"
            
            # Crear mensaje HTML
            html_body = f"""
            <html dir="ltr">
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 5px; text-align: center; }}
                    .content {{ background: #f9f9f9; padding: 20px; border-radius: 5px; margin: 15px 0; }}
                    .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 15px 0; font-weight: bold; }}
                    .info {{ background: #e8f4f8; padding: 15px; border-left: 4px solid #667eea; margin: 15px 0; border-radius: 3px; }}
                    .footer {{ color: #999; font-size: 12px; text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>NOVA Personal</h2>
                        <p>Control de Horas Extra en Línea</p>
                    </div>
                    
                    <div class="content">
                        <p>Estimado/a <strong>{n['supervisor_nombre']}</strong>,</p>
                        
                        <p>Como parte del piloto de Control HE en Línea NOVA, se han detectado <strong>{n['eventos_pendientes']} eventos de horas extra pendientes</strong> en el departamento de <strong>{n['departamento']}</strong>.</p>
                        
                        <p>Accede al panel para revisar, autorizar o ajustar estos eventos:</p>
                        
                        <div style="text-align: center;">
                            <a href="{panel_url}" class="button">Acceder al Panel de Control</a>
                        </div>
                        
                        <div class="info">
                            <strong>📊 Resumen:</strong>
                            <ul style="margin: 10px 0; padding-left: 20px;">
                                <li>Eventos pendientes: <strong>{n['eventos_pendientes']}</strong></li>
                                <li>Departamento: <strong>{n['departamento']}</strong></li>
                                <li>Acción requerida: Revisar y autorizar</li>
                            </ul>
                        </div>
                        
                        <p style="color: #666; font-size: 12px;">
                            <strong>Nota:</strong> Este enlace es privado y caduca en 7 días. Si no puedes acceder, contacta al administrador del sistema.
                        </p>
                    </div>
                    
                    <div class="footer">
                        <p>Sistema NOVA Personal - Control de Horas Extra</p>
                        <p>&copy; 2026 Wyny. Todos los derechos reservados.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEText(html_body, "html", "utf-8")
            msg["Subject"] = n["asunto"]
            msg["From"] = smtp_from
            msg["To"] = n["destino"]
            msg["Cc"] = "cesar_iracheta@wyny.com.mx"
            
            # Enviar email
            destinatarios = [n["destino"], "cesar_iracheta@wyny.com.mx"]
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # No usar STARTTLS en puertos 25 y 587
                if smtp_port not in (25, 587):
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg, to_addrs=destinatarios)
            
            # Actualizar estado a ENVIADA
            conn.execute(
                text("""
                    UPDATE ni_he_notificaciones_revision
                    SET estatus = 'ENVIADA',
                        fecha_envio = GETDATE(),
                        error_envio = NULL
                    WHERE id = :id
                """),
                {"id": n["id"]}
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "mensaje": f"Correo enviado a {n['destino']} ({n['supervisor_nombre']})",
                    "notificacion_id": n["id"]
                }
            )
            
    except Exception as ex:
        # Registrar error en BD
        try:
            with engine.begin() as conn:
                if n and n.get("id"):
                    conn.execute(
                        text("""
                            UPDATE ni_he_notificaciones_revision
                            SET estatus = 'ERROR',
                                error_envio = :error
                            WHERE id = :id
                        """),
                        {"id": n["id"], "error": str(ex)[:1000]}
                    )
        except:
            pass
        
        return JSONResponse(
            status_code=500,
            content={"ok": False, "mensaje": f"Error: {str(ex)}"}
        )
