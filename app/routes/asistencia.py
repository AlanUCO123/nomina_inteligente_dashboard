from datetime import date, timedelta

from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.database import engine

router = APIRouter()

# Templates se obtiene de app.main
templates = None

def set_templates(tmpl):
    global templates
    templates = tmpl

def obtener_periodo_miercoles_martes(fecha_base: date | None = None):
    """
    Obtiene el periodo miércoles -> martes que contiene la fecha indicada.
    Si no se indica fecha, usa el día actual.
    """
    fecha_base = fecha_base or date.today()

    dias_desde_miercoles = (fecha_base.weekday() - 2) % 7

    fecha_inicio = fecha_base - timedelta(days=dias_desde_miercoles)
    fecha_fin = fecha_inicio + timedelta(days=6)

    return fecha_inicio.isoformat(), fecha_fin.isoformat()

def puede_ver_checadas_empleado(
    numero_empleado_objetivo: str,
    numero_empleado_sesion: str | None,
    roles: list[str],
) -> bool:
    """
    Valida si el usuario de la sesión puede consultar las checadas
    del empleado solicitado.

    ADMIN/SISTEMAS/RH/NOMINA -> toda la empresa
    DIRECTOR -> empleados de su dirección
    GERENTE -> empleados de su gerencia
    SUPERVISOR -> empleados que le reportan
    EMPLEADO -> únicamente él mismo
    """

    if not numero_empleado_sesion:
        return False

    objetivo = str(numero_empleado_objetivo).strip()
    sesion = str(numero_empleado_sesion).strip()

    # Cualquier usuario puede consultar sus propias checadas.
    if objetivo == sesion:
        return True

    # Roles administrativos: acceso general.
    if any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"]
    ):
        return True

    # IMPORTANTE:
    # los roles son acumulativos, por eso evaluamos
    # DIRECTOR > GERENTE > SUPERVISOR.
    if "DIRECTOR" in roles:
        campo_jerarquia = "director"

    elif "GERENTE" in roles:
        campo_jerarquia = "gerente"

    elif "SUPERVISOR" in roles:
        campo_jerarquia = "reporta_a"

    else:
        return False

    sql = text(f"""
        SELECT TOP 1
            1
        FROM dbo.ni_empleados_maestro
        WHERE CAST(numero_empleado AS VARCHAR(50))
              = CAST(:numero_empleado_objetivo AS VARCHAR(50))

          AND CAST({campo_jerarquia} AS VARCHAR(50))
              = CAST(:numero_empleado_sesion AS VARCHAR(50))

          AND ISNULL(activo_intelisis, 1) = 1
    """)

    with engine.connect() as conn:
        permitido = conn.execute(
            sql,
            {
                "numero_empleado_objetivo": objetivo,
                "numero_empleado_sesion": sesion,
            }
        ).scalar()

    return bool(permitido)

@router.get("/asistencia/mis-checadas")
def mis_checadas(
    request: Request,
    fecha_inicio: str | None = Query(None),
    fecha_fin: str | None = Query(None),
    numero_empleado_param: str | None = Query(None, alias="numero_empleado")
):
    fecha_inicio_default, fecha_fin_default = obtener_periodo_miercoles_martes()

    fecha_inicio = fecha_inicio or fecha_inicio_default
    fecha_fin = fecha_fin or fecha_fin_default

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    es_admin = any(rol in roles for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"])
    es_director = "DIRECTOR" in roles
    es_gerente = "GERENTE" in roles
    es_supervisor = "SUPERVISOR" in roles

    # Determinar qué empleado se va a consultar.
    numero_empleado_a_ver = (
        str(numero_empleado_param).strip()
        if numero_empleado_param
        else str(numero_empleado_sesion).strip()
    )

    # Validar que el usuario realmente tenga permiso
    # para consultar a ese empleado.
    if not puede_ver_checadas_empleado(
        numero_empleado_a_ver,
        numero_empleado_sesion,
        roles,
    ):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "mensaje": "No tienes permiso para consultar las checadas de este empleado.",
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
        })

    sql_datos = text("""
        SELECT TOP 1
            numero_empleado,
            nombre_completo,
            deptop,
            departamento_intelisis,
            puesto_intelisis,
            categoria,
            nombre_reporta_a,
            nombre_gerente,
            nombre_director
        FROM ni_empleados_maestro
        WHERE numero_empleado = :numero_empleado
    """)

    sql_detalle = text("""
        SELECT
            a.jornada_id,
            a.fecha_operativa,
            a.dia_semana,
            a.numero_empleado,
            a.nombre_completo,
            a.deptop,
            a.puesto_intelisis,
            a.categoria,

            a.entrada_esperada,
            a.salida_esperada,
            a.primera_checada,
            a.ultima_checada,
            a.checada_entrada_valida,
            a.checada_salida_valida,

            a.estatus_asistencia,
            a.es_descanso,

            a.tipo_tiempo_extra,
            a.horas_extra_detectadas,
            a.estatus_he,
            a.horas_finales,

            a.observacion_sistema,

            -- Información nueva del proyecto del gerente
            nom.estatus_ejecutivo,
            nom.semaforo,
            nom.tipo_permiso,
            nom.permiso_nombre,
            nom.tipo_incidencia_nomina,
            nom.horas_a_descontar,
            nom.motivo_descuento,
            nom.observacion_ejecutiva,

            CASE
                WHEN a.fecha_operativa = CAST(GETDATE() AS date)
                THEN 1
                ELSE 0
            END AS es_hoy,

            CASE
                WHEN a.fecha_operativa > CAST(GETDATE() AS date)
                THEN 1
                ELSE 0
            END AS es_futuro

        FROM dbo.vw_ni_asistencia_checadas a

        OUTER APPLY (
            SELECT TOP (1)
                n.estatus_ejecutivo,
                n.semaforo,
                n.tipo_permiso,
                n.permiso_nombre,
                n.tipo_incidencia_nomina,
                n.horas_a_descontar,
                n.motivo_descuento,
                n.observacion_ejecutiva

            FROM dbo.vw_ni_incidencias_nomina_dia n

            WHERE n.numero_empleado = a.numero_empleado
            AND n.fecha_operativa = a.fecha_operativa
        ) nom

        WHERE a.numero_empleado = :numero_empleado
        AND a.fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin

        ORDER BY a.fecha_operativa
    """)

    sql_kpis = text("""
        SELECT
            COUNT(*) AS dias_calendario,
            SUM(CASE WHEN estatus_asistencia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS dias_en_tiempo,
            SUM(CASE WHEN estatus_asistencia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_asistencia IN ('FALTA', 'FALTA_ENTRADA') THEN 1 ELSE 0 END) AS faltas,
            SUM(CASE WHEN estatus_asistencia = 'DESCANSO' THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN estatus_asistencia = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_asistencia = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,
            SUM(
                CASE
                    WHEN checada_salida_valida IS NULL
                    AND checada_entrada_valida IS NOT NULL
                    AND salida_esperada IS NOT NULL
                    AND GETDATE() > salida_esperada
                    AND ISNULL(es_descanso, 0) = 0
                    THEN 1
                    ELSE 0
                END
            ) AS sin_salida,
            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_finales, 0)) AS DECIMAL(10,2)) AS he_final
        FROM vw_ni_asistencia_checadas
        WHERE numero_empleado = :numero_empleado
          AND fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
    """)

    params = {
        "numero_empleado": numero_empleado_a_ver,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin
    }

    with engine.begin() as conn:
        mis_datos = conn.execute(sql_datos, {
            "numero_empleado": numero_empleado_a_ver
        }).mappings().first()

        checadas = conn.execute(sql_detalle, params).mappings().all()
        kpis = conn.execute(sql_kpis, params).mappings().first()

    return templates.TemplateResponse("asistencia_mis_checadas.html", {
        "request": request,

        "login_user": login_user,
        "nombre_usuario": nombre_usuario,
        "numero_empleado": numero_empleado_sesion,
        "roles": roles,

        "mis_datos": mis_datos,
        "checadas": checadas,
        "kpis": kpis,

        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin
    })


@router.get("/asistencia/personal")
def checadas_personal(
    request: Request,
    fecha_inicio: str | None = Query(None),
    fecha_fin: str | None = Query(None),
    nivel: str = Query("EMPLEADOS"),
    departamento: str = Query("TODOS")
):
    fecha_inicio_default, fecha_fin_default = obtener_periodo_miercoles_martes()

    fecha_inicio = fecha_inicio or fecha_inicio_default
    fecha_fin = fecha_fin or fecha_fin_default

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    es_admin = any(rol in roles for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"])
    es_director = "DIRECTOR" in roles
    es_gerente = "GERENTE" in roles
    es_supervisor = "SUPERVISOR" in roles

    niveles_disponibles = []

    if es_admin:
        niveles_disponibles = ["DIRECTORES", "GERENTES", "SUPERVISORES", "EMPLEADOS"]
    elif es_director:
        niveles_disponibles = ["GERENTES", "SUPERVISORES", "EMPLEADOS"]
    elif es_gerente:
        niveles_disponibles = ["SUPERVISORES", "EMPLEADOS"]
    elif es_supervisor:
        niveles_disponibles = ["EMPLEADOS"]
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "mensaje": "No tienes permiso para consultar checadas del personal.",
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        })

    if nivel not in niveles_disponibles:
        nivel = niveles_disponibles[-1]

    scope_sql = ""
    params = {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "numero_empleado_sesion": numero_empleado,
        "departamento": departamento
    }

    if es_admin:
        scope_sql = ""
    elif es_director:
        scope_sql = "AND director = :numero_empleado_sesion"
    elif es_gerente:
        scope_sql = "AND gerente = :numero_empleado_sesion"
    elif es_supervisor:
        scope_sql = "AND reporta_a = :numero_empleado_sesion"

    departamento_sql = ""
    if departamento != "TODOS":
        departamento_sql = "AND deptop = :departamento"

    if nivel == "GERENTES":
        group_fields = """
            gerente AS clave,
            nombre_gerente AS nombre,
            'GERENTE' AS nivel,
            MAX(deptop) AS departamento
        """
        group_by = "gerente, nombre_gerente"

    elif nivel == "SUPERVISORES":
        group_fields = """
            reporta_a AS clave,
            nombre_reporta_a AS nombre,
            'SUPERVISOR' AS nivel,
            MAX(deptop) AS departamento
        """
        group_by = "reporta_a, nombre_reporta_a"

    elif nivel == "DIRECTORES":
        group_fields = """
            director AS clave,
            nombre_director AS nombre,
            'DIRECTOR' AS nivel,
            MAX(deptop) AS departamento
        """
        group_by = "director, nombre_director"

    else:
        group_fields = """
            numero_empleado AS clave,
            nombre_completo AS nombre,
            'EMPLEADO' AS nivel,
            MAX(deptop) AS departamento
        """
        group_by = "numero_empleado, nombre_completo"

    sql_resumen = text(f"""
        SELECT
            {group_fields},

            COUNT(DISTINCT numero_empleado) AS empleados,
            COUNT(*) AS dias_calendario,

            SUM(CASE WHEN estatus_asistencia = 'EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_asistencia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_asistencia IN ('FALTA', 'FALTA_ENTRADA') THEN 1 ELSE 0 END) AS faltas,
            SUM(CASE WHEN estatus_asistencia = 'DESCANSO' THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN checada_salida_valida IS NULL 
                      AND entrada_esperada IS NOT NULL 
                      AND ISNULL(es_descanso, 0) = 0 
                     THEN 1 ELSE 0 END) AS sin_salida,

            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_finales, 0)) AS DECIMAL(10,2)) AS he_final,

            SUM(CASE WHEN estatus_he = 'PENDIENTE' THEN 1 ELSE 0 END) AS he_pendiente,
            SUM(CASE WHEN estatus_he = 'CONFIRMADA' THEN 1 ELSE 0 END) AS he_confirmada

        FROM vw_ni_asistencia_checadas
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {scope_sql}
          {departamento_sql}
          AND numero_empleado IS NOT NULL
        GROUP BY {group_by}
        ORDER BY nombre
    """)

    sql_kpis = text(f"""
        SELECT
            COUNT(DISTINCT numero_empleado) AS empleados,
            SUM(CASE WHEN estatus_asistencia = 'RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_asistencia IN ('FALTA', 'FALTA_ENTRADA') THEN 1 ELSE 0 END) AS faltas,
            SUM(CASE WHEN checada_salida_valida IS NULL 
                      AND entrada_esperada IS NOT NULL 
                      AND ISNULL(es_descanso, 0) = 0 
                     THEN 1 ELSE 0 END) AS sin_salida,
            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_finales, 0)) AS DECIMAL(10,2)) AS he_final,
            SUM(CASE WHEN estatus_he = 'PENDIENTE' THEN 1 ELSE 0 END) AS he_pendiente
        FROM vw_ni_asistencia_checadas
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {scope_sql}
          {departamento_sql}
    """)

    sql_departamentos = text(f"""
        SELECT DISTINCT deptop
        FROM vw_ni_asistencia_checadas
        WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
          {scope_sql}
          AND deptop IS NOT NULL
        ORDER BY deptop
    """)

    with engine.begin() as conn:
        resumen = conn.execute(sql_resumen, params).mappings().all()
        kpis = conn.execute(sql_kpis, params).mappings().first()
        departamentos = conn.execute(sql_departamentos, params).scalars().all()

    return templates.TemplateResponse("asistencia_personal.html", {
        "request": request,

        "login_user": login_user,
        "nombre_usuario": nombre_usuario,
        "numero_empleado": numero_empleado,
        "roles": roles,

        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "nivel": nivel,
        "niveles_disponibles": niveles_disponibles,
        "departamento": departamento,
        "departamentos": departamentos,

        "resumen": resumen,
        "kpis": kpis,
        "es_admin": es_admin,
        "es_director": es_director,
        "es_gerente": es_gerente,
        "es_supervisor": es_supervisor
    })


@router.get("/asistencia/reporte-diario")
def reporte_diario(
    request: Request,
    fecha: str | None = Query(None),
    departamento: str = Query("TODOS"),
    tipo_horario: str = Query("TODOS"),
    grupo_horario: str = Query("TODOS"),
    semaforo: str = Query("TODOS")
):
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    # SUPERVISOR y GERENTE pueden consultar reportes.
    # ADMIN tiene acceso total.
    if (
        "SUPERVISOR" not in roles
        and "GERENTE" not in roles
        and "ADMIN" not in roles
    ):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "mensaje": (
                    "No tienes permiso para acceder "
                    "al Reporte diario."
                ),
                "login_user": login_user,
                "nombre_usuario": nombre_usuario,
                "numero_empleado": numero_empleado,
                "roles": roles,
            },
            status_code=403,
        )

    # Si el usuario entra sin seleccionar fecha,
    # mostrar automáticamente el día actual.
    if not fecha:
        fecha = date.today().isoformat()

    # Obtener la semana miércoles -> martes
    # correspondiente a la fecha del reporte.
    try:
        fecha_reporte = date.fromisoformat(fecha)
    except ValueError:
        fecha_reporte = date.today()
        fecha = fecha_reporte.isoformat()

    fecha_inicio_semana, fecha_fin_semana = (
        obtener_periodo_miercoles_martes(fecha_reporte)
    )

    es_admin = any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"]
    )

    es_director = "DIRECTOR" in roles
    es_gerente = "GERENTE" in roles
    es_supervisor = "SUPERVISOR" in roles

    scope_sql = ""
    params = {
        "fecha": fecha,
        "numero_empleado_sesion": numero_empleado,
        "departamento": departamento,
        "tipo_horario": tipo_horario,
        "grupo_horario": grupo_horario,
        "semaforo": semaforo
    }

    if es_admin:
        scope_sql = ""
    elif es_director:
        scope_sql = "AND director = :numero_empleado_sesion"
    elif es_gerente:
        scope_sql = "AND gerente = :numero_empleado_sesion"
    elif es_supervisor:
        scope_sql = "AND reporta_a = :numero_empleado_sesion"
    else:
        scope_sql = "AND numero_empleado = :numero_empleado_sesion"

    filtros_sql = ""

    if departamento != "TODOS":
        filtros_sql += " AND departamento = :departamento"

    if tipo_horario != "TODOS":
        filtros_sql += " AND tipo_horario = :tipo_horario"

    if grupo_horario != "TODOS":
        filtros_sql += " AND grupo_horario = :grupo_horario"

    if semaforo != "TODOS":
        filtros_sql += " AND semaforo = :semaforo"

    sql_kpis = text(f"""
        WITH datos_filtrados AS (
            SELECT TOP 50000
                estatus_ejecutivo,
                horas_extra_detectadas,
                horas_he_finales,
                estatus_he,
                semaforo
            FROM vw_ni_reporte_asistencia_dia_base
            WHERE fecha_operativa = :fecha
              {scope_sql}
              {filtros_sql}
        )
        SELECT
            COUNT(*) AS plantilla,

            SUM(CASE WHEN estatus_ejecutivo IN (
                'PRESENTE_EN_TIEMPO',
                'PRESENTE_CON_RETARDO',
                'SIN_SALIDA'
            ) THEN 1 ELSE 0 END) AS presentes,

            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO' THEN 1 ELSE 0 END) AS retardos,

            SUM(CASE WHEN estatus_ejecutivo = 'SIN_ENTRADA' THEN 1 ELSE 0 END) AS sin_entrada,
            SUM(CASE WHEN estatus_ejecutivo = 'SIN_SALIDA' THEN 1 ELSE 0 END) AS sin_salida,

            SUM(CASE WHEN estatus_ejecutivo IN ('DESCANSO', 'DESCANSO_CON_HE') THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN estatus_ejecutivo = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_ejecutivo = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,

            SUM(CASE WHEN horas_extra_detectadas > 0 THEN 1 ELSE 0 END) AS empleados_con_he,
            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_he_finales, 0)) AS DECIMAL(10,2)) AS he_final,

            SUM(CASE WHEN estatus_he = 'PENDIENTE' THEN 1 ELSE 0 END) AS he_pendiente,
            SUM(CASE WHEN estatus_he = 'CONFIRMADA' THEN 1 ELSE 0 END) AS he_confirmada,

            SUM(CASE WHEN semaforo = 'ROJO' THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN semaforo = 'AMARILLO' THEN 1 ELSE 0 END) AS pendientes_revision,
            SUM(CASE WHEN semaforo = 'VERDE' THEN 1 ELSE 0 END) AS verdes,
            SUM(CASE WHEN semaforo = 'GRIS' THEN 1 ELSE 0 END) AS grises

        FROM datos_filtrados
    """)

    sql_por_horario = text(f"""
        WITH datos_filtrados AS (
            SELECT TOP 50000
                tipo_horario,
                grupo_horario,
                estatus_ejecutivo,
                horas_extra_detectadas,
                horas_he_finales,
                estatus_he,
                semaforo
            FROM vw_ni_reporte_asistencia_dia_base
            WHERE fecha_operativa = :fecha
              {scope_sql}
              {filtros_sql}
        )
        SELECT
            tipo_horario,
            grupo_horario,

            COUNT(*) AS empleados,

            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_ejecutivo = 'SIN_ENTRADA' THEN 1 ELSE 0 END) AS sin_entrada,
            SUM(CASE WHEN estatus_ejecutivo = 'SIN_SALIDA' THEN 1 ELSE 0 END) AS sin_salida,

            SUM(CASE WHEN estatus_ejecutivo IN ('DESCANSO', 'DESCANSO_CON_HE') THEN 1 ELSE 0 END) AS descansos,
            SUM(CASE WHEN estatus_ejecutivo = 'VACACIONES' THEN 1 ELSE 0 END) AS vacaciones,
            SUM(CASE WHEN estatus_ejecutivo = 'PERMISO' THEN 1 ELSE 0 END) AS permisos,

            SUM(CASE WHEN horas_extra_detectadas > 0 THEN 1 ELSE 0 END) AS empleados_con_he,
            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_he_finales, 0)) AS DECIMAL(10,2)) AS he_final,

            SUM(CASE WHEN estatus_he = 'PENDIENTE' THEN 1 ELSE 0 END) AS he_pendiente,
            SUM(CASE WHEN estatus_he = 'CONFIRMADA' THEN 1 ELSE 0 END) AS he_confirmada,

            SUM(CASE WHEN semaforo = 'ROJO' THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN semaforo = 'AMARILLO' THEN 1 ELSE 0 END) AS pendientes_revision

        FROM datos_filtrados
        GROUP BY
            tipo_horario,
            grupo_horario
        ORDER BY
            empleados DESC
    """)

    sql_por_departamento = text(f"""
        WITH datos_filtrados AS (
            SELECT TOP 50000
                departamento,
                estatus_ejecutivo,
                horas_extra_detectadas,
                horas_he_finales,
                estatus_he,
                semaforo
            FROM vw_ni_reporte_asistencia_dia_base
            WHERE fecha_operativa = :fecha
              {scope_sql}
              {filtros_sql}
        )
        SELECT
            departamento,

            COUNT(*) AS plantilla,

            SUM(CASE WHEN estatus_ejecutivo IN (
                'PRESENTE_EN_TIEMPO',
                'PRESENTE_CON_RETARDO',
                'SIN_SALIDA'
            ) THEN 1 ELSE 0 END) AS presentes,

            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_EN_TIEMPO' THEN 1 ELSE 0 END) AS en_tiempo,
            SUM(CASE WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO' THEN 1 ELSE 0 END) AS retardos,
            SUM(CASE WHEN estatus_ejecutivo = 'SIN_ENTRADA' THEN 1 ELSE 0 END) AS sin_entrada,
            SUM(CASE WHEN estatus_ejecutivo = 'SIN_SALIDA' THEN 1 ELSE 0 END) AS sin_salida,

            SUM(CASE WHEN horas_extra_detectadas > 0 THEN 1 ELSE 0 END) AS empleados_con_he,
            CAST(SUM(ISNULL(horas_extra_detectadas, 0)) AS DECIMAL(10,2)) AS he_detectada,
            CAST(SUM(ISNULL(horas_he_finales, 0)) AS DECIMAL(10,2)) AS he_final,

            SUM(CASE WHEN estatus_he = 'PENDIENTE' THEN 1 ELSE 0 END) AS he_pendiente,

            SUM(CASE WHEN semaforo = 'ROJO' THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN semaforo = 'AMARILLO' THEN 1 ELSE 0 END) AS pendientes_revision

        FROM datos_filtrados
        GROUP BY
            departamento
        ORDER BY
            criticos DESC,
            pendientes_revision DESC,
            departamento
    """)

    sql_detalle = text(f"""
        SELECT TOP 100
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            tipo_horario,
            grupo_horario,
            nombre_reporta_a AS supervisor,
            nombre_gerente AS gerente,
            entrada_esperada,
            checada_entrada_valida,
            salida_esperada,
            checada_salida_valida,
            estatus_dia,
            estatus_ejecutivo,
            semaforo,
            horas_extra_detectadas,
            estatus_he,
            horas_he_finales,
            observacion_ejecutiva
        FROM vw_ni_reporte_asistencia_dia_base
        WHERE fecha_operativa = :fecha
          {scope_sql}
          {filtros_sql}
          AND semaforo IN ('ROJO', 'AMARILLO')
        ORDER BY
            CASE semaforo
                WHEN 'ROJO' THEN 1
                WHEN 'AMARILLO' THEN 2
                ELSE 3
            END,
            departamento,
            nombre_completo
    """)

    sql_departamentos = text(f"""
        SELECT DISTINCT TOP 100 departamento
        FROM vw_ni_reporte_asistencia_dia_base
        WHERE fecha_operativa = :fecha
          {scope_sql}
          AND departamento IS NOT NULL
        ORDER BY departamento
    """)

    sql_grupos = text(f"""
        SELECT DISTINCT TOP 100 grupo_horario
        FROM vw_ni_reporte_asistencia_dia_base
        WHERE fecha_operativa = :fecha
          {scope_sql}
          AND grupo_horario IS NOT NULL
        ORDER BY grupo_horario
    """)

    with engine.begin() as conn:
        kpis = conn.execute(sql_kpis, params).mappings().first()
        por_horario = conn.execute(sql_por_horario, params).mappings().all()
        por_departamento = conn.execute(sql_por_departamento, params).mappings().all()
        detalle = conn.execute(sql_detalle, params).mappings().all()
        departamentos = conn.execute(sql_departamentos, params).scalars().all()
        grupos_horario = conn.execute(sql_grupos, params).scalars().all()

    return templates.TemplateResponse("asistencia_reporte_diario.html", {
        "request": request,

        "login_user": login_user,
        "nombre_usuario": nombre_usuario,
        "numero_empleado": numero_empleado,
        "roles": roles,

        "fecha": fecha,
        "fecha_inicio_semana": fecha_inicio_semana,
        "fecha_fin_semana": fecha_fin_semana,

        "departamento": departamento,
        "tipo_horario": tipo_horario,
        "grupo_horario": grupo_horario,
        "semaforo": semaforo,

        "kpis": kpis,
        "por_horario": por_horario,
        "por_departamento": por_departamento,
        "detalle": detalle,

        "departamentos": departamentos,
        "grupos_horario": grupos_horario
    })

@router.get("/asistencia/resumen-semanal")
def resumen_semanal(
    request: Request,
    fecha_inicio: str | None = Query(None),
    departamento: str = Query("TODOS")
):
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    # SUPERVISOR y GERENTE pueden consultar reportes.
    # ADMIN tiene acceso total.
    if (
        "SUPERVISOR" not in roles
        and "GERENTE" not in roles
        and "ADMIN" not in roles
    ):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "mensaje": (
                    "No tienes permiso para acceder "
                    "al Reporte diario."
                ),
                "login_user": login_user,
                "nombre_usuario": nombre_usuario,
                "numero_empleado": numero_empleado,
                "roles": roles,
            },
            status_code=403,
        )

    # ---------------------------------------------------------
    # PERIODO MIÉRCOLES -> MARTES
    # ---------------------------------------------------------
    try:
        fecha_base = (
            date.fromisoformat(fecha_inicio)
            if fecha_inicio
            else date.today()
        )
    except ValueError:
        fecha_base = date.today()

    fecha_inicio, fecha_fin = obtener_periodo_miercoles_martes(
        fecha_base
    )

    fecha_inicio_date = date.fromisoformat(fecha_inicio)
    fecha_fin_date = date.fromisoformat(fecha_fin)

    # Si estamos viendo la semana actual, no contamos días futuros.
    hoy = date.today()

    if fecha_inicio_date <= hoy <= fecha_fin_date:
        fecha_corte = hoy.isoformat()
    else:
        fecha_corte = fecha_fin

    # ---------------------------------------------------------
    # ALCANCE POR ROL
    # ---------------------------------------------------------
    es_admin = any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"]
    )

    es_director = "DIRECTOR" in roles
    es_gerente = "GERENTE" in roles
    es_supervisor = "SUPERVISOR" in roles

    if es_admin:
        scope_sql = ""

    elif es_director:
        scope_sql = """
            AND director = :numero_empleado_sesion
        """

    elif es_gerente:
        scope_sql = """
            AND gerente = :numero_empleado_sesion
        """

    elif es_supervisor:
        scope_sql = """
            AND reporta_a = :numero_empleado_sesion
        """

    else:
        scope_sql = """
            AND numero_empleado = :numero_empleado_sesion
        """

    departamento_sql = ""

    if departamento != "TODOS":
        departamento_sql = """
            AND departamento = :departamento
        """

    params = {
        "fecha_inicio": fecha_inicio,
        "fecha_corte": fecha_corte,
        "numero_empleado_sesion": numero_empleado,
        "departamento": departamento,
    }

    # ---------------------------------------------------------
    # KPIs GENERALES
    # ---------------------------------------------------------
    sql_kpis = text(f"""
        SELECT
            COUNT(DISTINCT numero_empleado) AS plantilla,

            SUM(
                CASE
                    WHEN estatus_ejecutivo IN (
                        'PRESENTE_EN_TIEMPO',
                        'PRESENTE_CON_RETARDO',
                        'SIN_SALIDA'
                    )
                    THEN 1 ELSE 0
                END
            ) AS asistencias,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO'
                    THEN 1 ELSE 0
                END
            ) AS retardos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_ENTRADA'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS sin_entrada,

            SUM(
                CASE
                    WHEN estatus_dia = 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_entrada,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_SALIDA'
                    THEN 1 ELSE 0
                END
            ) AS sin_salida,

            SUM(
                CASE
                    WHEN estatus_ejecutivo IN (
                        'DESCANSO',
                        'DESCANSO_CON_HE'
                    )
                    THEN 1 ELSE 0
                END
            ) AS descansos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'VACACIONES'
                    THEN 1 ELSE 0
                END
            ) AS vacaciones,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PERMISO'
                    THEN 1 ELSE 0
                END
            ) AS permisos,

            CAST(
                SUM(ISNULL(horas_extra_detectadas, 0))
                AS DECIMAL(10,2)
            ) AS he_detectada,

            CAST(
                SUM(
                    CASE
                        WHEN estatus_he IN ('CONFIRMADA', 'AJUSTADA')
                        THEN ISNULL(horas_he_finales, 0)
                        ELSE 0
                    END
                )
                AS DECIMAL(10,2)
            ) AS he_autorizada,

            SUM(
                CASE
                    WHEN estatus_he = 'PENDIENTE'
                    THEN 1 ELSE 0
                END
            ) AS he_pendiente,

            SUM(
                CASE
                    WHEN semaforo = 'ROJO'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS criticos,

            SUM(
                CASE
                    WHEN semaforo = 'AMARILLO'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_revision

        FROM dbo.vw_ni_reporte_asistencia_dia_base

        WHERE fecha_operativa
              BETWEEN :fecha_inicio AND :fecha_corte

          {scope_sql}
          {departamento_sql}
    """)

    # ---------------------------------------------------------
    # RESUMEN DÍA POR DÍA
    # ---------------------------------------------------------
    sql_por_dia = text(f"""
        SELECT
            fecha_operativa,

            COUNT(DISTINCT numero_empleado) AS plantilla,

            SUM(
                CASE
                    WHEN estatus_ejecutivo IN (
                        'PRESENTE_EN_TIEMPO',
                        'PRESENTE_CON_RETARDO',
                        'SIN_SALIDA'
                    )
                    THEN 1 ELSE 0
                END
            ) AS presentes,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PRESENTE_EN_TIEMPO'
                    THEN 1 ELSE 0
                END
            ) AS en_tiempo,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO'
                    THEN 1 ELSE 0
                END
            ) AS retardos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_ENTRADA'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS sin_entrada,

            SUM(
                CASE
                    WHEN estatus_dia = 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_entrada,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_SALIDA'
                    THEN 1 ELSE 0
                END
            ) AS sin_salida,

            SUM(
                CASE
                    WHEN estatus_ejecutivo IN (
                        'DESCANSO',
                        'DESCANSO_CON_HE'
                    )
                    THEN 1 ELSE 0
                END
            ) AS descansos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'VACACIONES'
                    THEN 1 ELSE 0
                END
            ) AS vacaciones,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PERMISO'
                    THEN 1 ELSE 0
                END
            ) AS permisos,

            CAST(
                SUM(ISNULL(horas_extra_detectadas, 0))
                AS DECIMAL(10,2)
            ) AS he_detectada,

            SUM(
                CASE
                    WHEN semaforo = 'ROJO'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS criticos,

            SUM(
                CASE
                    WHEN semaforo = 'AMARILLO'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_revision

        FROM dbo.vw_ni_reporte_asistencia_dia_base

        WHERE fecha_operativa
              BETWEEN :fecha_inicio AND :fecha_corte

          {scope_sql}
          {departamento_sql}

        GROUP BY fecha_operativa

        ORDER BY fecha_operativa
    """)

    # ---------------------------------------------------------
    # RESUMEN POR DEPARTAMENTO
    # ---------------------------------------------------------
    sql_por_departamento = text(f"""
        SELECT
            departamento,

            COUNT(DISTINCT numero_empleado) AS empleados,

            SUM(
                CASE
                    WHEN estatus_ejecutivo IN (
                        'PRESENTE_EN_TIEMPO',
                        'PRESENTE_CON_RETARDO',
                        'SIN_SALIDA'
                    )
                    THEN 1 ELSE 0
                END
            ) AS asistencias,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO'
                    THEN 1 ELSE 0
                END
            ) AS retardos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_ENTRADA'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS sin_entrada,

            SUM(
                CASE
                    WHEN estatus_dia = 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_entrada,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_SALIDA'
                    THEN 1 ELSE 0
                END
            ) AS sin_salida,

            CAST(
                SUM(ISNULL(horas_extra_detectadas, 0))
                AS DECIMAL(10,2)
            ) AS he_detectada,

            SUM(
                CASE
                    WHEN semaforo = 'ROJO'
                    AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS criticos,

            SUM(
                CASE
                    WHEN semaforo = 'AMARILLO'
                    THEN 1 ELSE 0
                END
            ) AS pendientes_revision

        FROM dbo.vw_ni_reporte_asistencia_dia_base

        WHERE fecha_operativa
              BETWEEN :fecha_inicio AND :fecha_corte

          {scope_sql}
          {departamento_sql}

        GROUP BY departamento

        ORDER BY
            criticos DESC,
            sin_entrada DESC,
            retardos DESC,
            departamento
    """)

    # ---------------------------------------------------------
    # EMPLEADOS CON INCIDENCIAS
    # ---------------------------------------------------------
    sql_incidencias = text(f"""
        SELECT TOP 50
            numero_empleado,
            nombre_completo,
            MAX(departamento) AS departamento,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO'
                    THEN 1 ELSE 0
                END
            ) AS retardos,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_ENTRADA'
                    THEN 1 ELSE 0
                END
            ) AS sin_entrada,

            SUM(
                CASE
                    WHEN estatus_ejecutivo = 'SIN_SALIDA'
                    THEN 1 ELSE 0
                END
            ) AS sin_salida,

            CAST(
                SUM(ISNULL(horas_extra_detectadas, 0))
                AS DECIMAL(10,2)
            ) AS he_detectada

        FROM dbo.vw_ni_reporte_asistencia_dia_base

        WHERE fecha_operativa
            BETWEEN :fecha_inicio AND :fecha_corte

        {scope_sql}
        {departamento_sql}

        AND ISNULL(estatus_dia, '') <> 'PENDIENTE_ENTRADA'

        GROUP BY
            numero_empleado,
            nombre_completo

        HAVING
               SUM(
                    CASE
                        WHEN estatus_ejecutivo = 'PRESENTE_CON_RETARDO'
                        THEN 1 ELSE 0
                    END
               ) > 0

            OR SUM(
                    CASE
                        WHEN estatus_ejecutivo = 'SIN_ENTRADA'
                        THEN 1 ELSE 0
                    END
               ) > 0

            OR SUM(
                    CASE
                        WHEN estatus_ejecutivo = 'SIN_SALIDA'
                        THEN 1 ELSE 0
                    END
               ) > 0

            OR SUM(ISNULL(horas_extra_detectadas, 0)) > 0

        ORDER BY
            sin_entrada DESC,
            retardos DESC,
            sin_salida DESC,
            he_detectada DESC,
            nombre_completo
    """)

    # ---------------------------------------------------------
    # DEPARTAMENTOS DISPONIBLES SEGÚN ALCANCE
    # ---------------------------------------------------------
    sql_departamentos = text(f"""
        SELECT DISTINCT departamento

        FROM dbo.vw_ni_reporte_asistencia_dia_base

        WHERE fecha_operativa
              BETWEEN :fecha_inicio AND :fecha_corte

          {scope_sql}

          AND departamento IS NOT NULL

        ORDER BY departamento
    """)

    with engine.begin() as conn:
        kpis = conn.execute(
            sql_kpis,
            params
        ).mappings().first()

        por_dia = conn.execute(
            sql_por_dia,
            params
        ).mappings().all()

        por_departamento = conn.execute(
            sql_por_departamento,
            params
        ).mappings().all()

        incidencias = conn.execute(
            sql_incidencias,
            params
        ).mappings().all()

        departamentos = conn.execute(
            sql_departamentos,
            params
        ).scalars().all()

    return templates.TemplateResponse(
        "asistencia_resumen_semanal.html",
        {
            "request": request,

            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,

            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "fecha_corte": fecha_corte,

            "departamento": departamento,
            "departamentos": departamentos,

            "kpis": kpis,
            "por_dia": por_dia,
            "por_departamento": por_departamento,
            "incidencias": incidencias,
        }
    )