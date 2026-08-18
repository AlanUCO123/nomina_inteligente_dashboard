from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from datetime import date, timedelta
import logging
import os

from app.database import engine, _serialize_value

logger = logging.getLogger(__name__)

router = APIRouter()

# Cargar templates
templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)

def periodo_default():
    """
    Regresa periodo miércoles-martes basado en la fecha actual.
    """
    hoy = date.today()

    # Python: Monday=0, Tuesday=1, Wednesday=2
    dias_desde_miercoles = (hoy.weekday() - 2) % 7
    fecha_inicio = hoy - timedelta(days=dias_desde_miercoles)
    fecha_fin = fecha_inicio + timedelta(days=6)

    return fecha_inicio, fecha_fin

@router.get("/horas-extra")
def horas_extra(
    request: Request,
    fecha_inicio: str | None = Query(None),
    fecha_fin: str | None = Query(None),
    departamento: str | None = Query(None),
    estatus: str | None = Query(None),
    solicitud_te: str = Query("TODAS"),
):

    # Datos de sesión para integrar esta pantalla al panel NOVA
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    # Esta pantalla ya forma parte del sistema autenticado
    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    es_admin = any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"]
    )

    if not fecha_inicio or not fecha_fin:
        fi, ff = periodo_default()
        fecha_inicio = fi.isoformat()
        fecha_fin = ff.isoformat()

    if departamento == "":
        departamento = None

    if estatus == "":
        estatus = None
    
    if solicitud_te == "":
        solicitud_te = "TODAS"

    # Calcular días del período
    fi_date = date.fromisoformat(fecha_inicio)
    ff_date = date.fromisoformat(fecha_fin)
    
    # Mapeo de días de la semana
    dias_nombres = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
    
    dias_periodo = []
    d = fi_date
    while d <= ff_date:
        dias_periodo.append({
            "fecha": d.isoformat(),
            "dia": dias_nombres[d.weekday()],  # 0=Monday, 2=Wednesday, 6=Sunday
            "label": f"{d.day:02d}",
            "numero_dia": d.day
        })
        d += timedelta(days=1)

    with engine.begin() as conn:

        # IMPORTANTE:
        # En esta copia del proyecto NO generamos ni actualizamos registros
        # automáticamente al consultar la pantalla.
        # Así podemos comparar contra el gerente sin modificar la BD compartida.
        #
        # El procedimiento sp_ni_generar_he_autorizacion_periodo hace MERGE,
        # por eso queda deshabilitado mientras validamos esta integración.
        pass

        # Detalle diario de HE
        detalle = conn.execute(
            text("""
                SELECT TOP 100
                    id,
                    fecha_operativa,
                    numero_empleado,
                    nombre_completo,
                    departamento,
                    categoria_intelisis,
                    aplica_he,
                    tipo_tiempo_extra_final,
                    CAST(ISNULL(minutos_detectados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
                    CAST(ISNULL(minutos_autorizados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas,
                    estatus,
                    estatus_autorizacion,
                    revisor_nombre,
                    revisor_email,
                    revisor_telefono,
                    autorizador_nombre,
                    autorizador_email,
                    autorizador_telefono,
                    notificador_nombre,
                    notificador_email,
                    notificador_telefono,
                    flujo_autorizacion,
                    motivo,
                    observaciones,
                    ISNULL(tiene_solicitud_te, 0) AS tiene_solicitud_te,
                    ISNULL(reclasificado_como_solicitado, 0) AS reclasificado_como_solicitado,
                    CASE
                        WHEN ISNULL(reclasificado_como_solicitado, 0) = 1 THEN 'RECLASIFICADA'
                        WHEN ISNULL(tiene_solicitud_te, 0) = 1 THEN 'CON_SOLICITUD'
                        ELSE 'SIN_SOLICITUD'
                    END AS grupo_solicitud_te
                FROM ni_horas_extra_autorizacion
                WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
                  AND ISNULL(aplica_he, 0) = 1
                  AND estatus NOT IN ('CANCELADO')
                  AND (:departamento IS NULL OR departamento = :departamento)
                  AND (:estatus IS NULL OR estatus = :estatus)
                  AND (
                        :solicitud_te = 'TODAS'

                     OR (
                            :solicitud_te = 'PROPUESTA'
                        AND (
                                ISNULL(tiene_solicitud_te, 0) = 1
                             OR ISNULL(reclasificado_como_solicitado, 0) = 1
                            )
                        )

                     OR (
                            :solicitud_te = 'CON_SOLICITUD'
                        AND ISNULL(tiene_solicitud_te, 0) = 1
                        )

                     OR (
                            :solicitud_te = 'SIN_SOLICITUD'
                        AND ISNULL(tiene_solicitud_te, 0) = 0
                        AND ISNULL(reclasificado_como_solicitado, 0) = 0
                        )

                     OR (
                            :solicitud_te = 'RECLASIFICADA'
                        AND ISNULL(reclasificado_como_solicitado, 0) = 1
                        )
                  )
                ORDER BY departamento, nombre_completo, fecha_operativa
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "departamento": departamento,
                "estatus": estatus,
                "solicitud_te": solicitud_te
            }
        ).mappings().all()

        # Cierre por empleado:
        # - Usa la misma lógica de cálculo que el gerente (sp_ni_he_cierre_periodo_v2)
        # - Conserva nuestro filtro/clasificación de Solicitud TE
        cierre = []

        try:
            # 1. Cierre oficial: misma lógica que utiliza el gerente
            cierre_v2 = conn.execute(
                text("""
                    EXEC sp_ni_he_cierre_periodo_v2
                        @fecha_inicio = :fecha_inicio,
                        @fecha_fin = :fecha_fin,
                        @departamento = :departamento
                """),
                {
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "departamento": departamento,
                }
            ).mappings().all()

            # 2. Obtener nuestra clasificación de Solicitud TE.
            # Se toman únicamente los registros que también participan
            # en el cierre V2.
            solicitud_rows = conn.execute(
                text("""
                    SELECT
                        h.numero_empleado,

                        MAX(
                            CAST(
                                ISNULL(h.tiene_solicitud_te, 0)
                                AS INT
                            )
                        ) AS tiene_solicitud_te,

                        MAX(
                            CAST(
                                ISNULL(
                                    h.reclasificado_como_solicitado,
                                    0
                                )
                                AS INT
                            )
                        ) AS reclasificado_como_solicitado

                    FROM ni_horas_extra_autorizacion h

                    WHERE h.fecha_operativa
                          BETWEEN :fecha_inicio AND :fecha_fin

                      AND ISNULL(h.aplica_he, 0) = 1

                      AND h.estatus IN (
                            'DETECTADA',
                            'CONFIRMADA',
                            'MODIFICADA',
                            'AGREGADA_MANUAL'
                      )

                      AND (
                            :departamento IS NULL
                            OR h.departamento = :departamento
                      )

                    GROUP BY
                        h.numero_empleado
                """),
                {
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "departamento": departamento,
                }
            ).mappings().all()

            # 3. Crear mapa de Solicitud TE por empleado
            solicitud_map = {}

            for s in solicitud_rows:
                numero = str(s["numero_empleado"])

                if int(
                    s["reclasificado_como_solicitado"] or 0
                ) == 1:
                    grupo = "RECLASIFICADA"

                elif int(
                    s["tiene_solicitud_te"] or 0
                ) == 1:
                    grupo = "CON_SOLICITUD"

                else:
                    grupo = "SIN_SOLICITUD"

                solicitud_map[numero] = grupo

            # 4. Combinar:
            # cierre oficial V2 + nuestras Solicitudes TE
            for row in cierre_v2:
                item = dict(row)

                numero = str(item["numero_empleado"])

                grupo = solicitud_map.get(
                    numero,
                    "SIN_SOLICITUD"
                )

                item["grupo_solicitud_te"] = grupo

                # 5. Mantener nuestros filtros actuales
                incluir = (
                    solicitud_te == "TODAS"

                    or (
                        solicitud_te == "PROPUESTA"
                        and grupo in (
                            "CON_SOLICITUD",
                            "RECLASIFICADA"
                        )
                    )

                    or (
                        solicitud_te == "CON_SOLICITUD"
                        and grupo == "CON_SOLICITUD"
                    )

                    or (
                        solicitud_te == "SIN_SOLICITUD"
                        and grupo == "SIN_SOLICITUD"
                    )

                    or (
                        solicitud_te == "RECLASIFICADA"
                        and grupo == "RECLASIFICADA"
                    )
                )

                if incluir:
                    cierre.append(item)

        except Exception as e:
            logger.error(
                f"Error en cierre V2: {e}",
                exc_info=True
            )

        # Departamentos para filtro
        departamentos = conn.execute(
            text("""
                SELECT DISTINCT departamento
                FROM ni_horas_extra_autorizacion
                WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
                  AND departamento IS NOT NULL
                ORDER BY departamento
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            }
        ).mappings().all()

        # Grid diario de HE
        grid_diario = conn.execute(
            text("""
                SELECT
                    fecha_operativa,
                    numero_empleado,
                    CAST(SUM(ISNULL(minutos_autorizados, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas,
                    MAX(tipo_tiempo_extra_final) AS tipo_tiempo_extra_final
                FROM vw_ni_he_grid_diario
                WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
                  AND (:departamento IS NULL OR departamento = :departamento)
                  AND (:estatus IS NULL OR estatus = :estatus)
                GROUP BY fecha_operativa, numero_empleado
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "departamento": departamento,
                "estatus": estatus
            }
        ).mappings().all()

        grid_map = {}
        for r in grid_diario:
            key = f"{r['numero_empleado']}_{r['fecha_operativa']}"
            grid_map[key] = {
                "horas": r["horas_autorizadas"],
                "tipo": r["tipo_tiempo_extra_final"]
            }

        # KPIs
        kpis = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS registros_he,
                    COUNT(DISTINCT numero_empleado) AS empleados_con_he,
                    CAST(SUM(ISNULL(minutos_autorizados, 0)) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas,
                    SUM(CASE WHEN estatus_autorizacion = 'PENDIENTE_AUTORIZACION' THEN 1 ELSE 0 END) AS pendientes,
                    SUM(CASE WHEN estatus = 'CONFIRMADA' THEN 1 ELSE 0 END) AS confirmadas,
                    SUM(CASE WHEN estatus = 'NO_CONSIDERAR' THEN 1 ELSE 0 END) AS no_considerar
                FROM ni_horas_extra_autorizacion
                WHERE fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
                  AND ISNULL(aplica_he, 0) = 1
                  AND (:departamento IS NULL OR departamento = :departamento)
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "departamento": departamento
            }
        ).mappings().first()

    return templates.TemplateResponse(
        request=request,
        name="horas_extra.html",
        context={
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "departamento": departamento,
            "estatus": estatus,
            "solicitud_te": solicitud_te,
            "departamentos": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in departamentos
            ],
            "detalle": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in detalle
            ],
            "cierre": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in cierre
            ],
            "kpis": {k: _serialize_value(v) for k, v in dict(kpis).items()} if kpis else {},
            "dias_periodo": dias_periodo,
            "grid_map": grid_map,

            # Contexto de sesión para base.html
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
            "usuario_actual": {
                "login_user": login_user,
                "numero_empleado": numero_empleado_sesion,
                "roles": roles,
                "es_admin": es_admin,
            },
        }
    )

@router.post("/horas-extra/confirmar")
def confirmar_he(
    id: int = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str | None = Form(None),
):
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE ni_horas_extra_autorizacion
                SET
                    estatus = 'CONFIRMADA',
                    estatus_autorizacion = 'AUTORIZADA_SISTEMA',
                    autorizado_por = 'usuario_actual',
                    fecha_autorizacion = GETDATE()
                WHERE id = :id
                  AND ISNULL(aplica_he, 0) = 1
            """),
            {"id": id}
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"

    return RedirectResponse(url=url, status_code=303)

@router.post("/horas-extra/no-considerar")
def no_considerar_he(
    id: int = Form(...),
    motivo: str = Form("No considerada por RH/Nóminas"),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str | None = Form(None),
):
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE ni_horas_extra_autorizacion
                SET
                    estatus = 'NO_CONSIDERAR',
                    estatus_autorizacion = 'NO_CONSIDERAR',
                    minutos_autorizados = 0,
                    minutos_dobles_autorizados = 0,
                    minutos_triples_autorizados = 0,
                    motivo = :motivo,
                    autorizado_por = 'usuario_actual',
                    fecha_autorizacion = GETDATE()
                WHERE id = :id
            """),
            {
                "id": id,
                "motivo": motivo
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"

    return RedirectResponse(url=url, status_code=303)

@router.post("/horas-extra/modificar")
def modificar_he(
    id: int = Form(...),
    horas_autorizadas: float = Form(...),
    tipo_tiempo_extra_final: str = Form(...),
    motivo: str = Form("Modificación manual RH/Nóminas"),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento: str | None = Form(None),
):
    minutos = int(round(horas_autorizadas * 60))

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE ni_horas_extra_autorizacion
                SET
                    estatus = 'MODIFICADA',
                    tipo_tiempo_extra_final = :tipo_tiempo_extra_final,
                    minutos_autorizados = :minutos,
                    motivo = :motivo,
                    autorizado_por = 'usuario_actual',
                    fecha_autorizacion = GETDATE()
                WHERE id = :id
                  AND ISNULL(aplica_he, 0) = 1
            """),
            {
                "id": id,
                "tipo_tiempo_extra_final": tipo_tiempo_extra_final,
                "minutos": minutos,
                "motivo": motivo
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"

    return RedirectResponse(url=url, status_code=303)

@router.post("/horas-extra/agregar")
def agregar_he(
    fecha_operativa: str = Form(...),
    numero_empleado: str = Form(...),
    horas_autorizadas: float = Form(...),
    tipo_tiempo_extra_final: str = Form(...),
    motivo: str = Form("HE agregada manualmente"),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    departamento_filtro: str | None = Form(None),
):
    minutos = int(round(horas_autorizadas * 60))

    with engine.begin() as conn:
        empleado = conn.execute(
            text("""
                SELECT TOP 1
                    numero_empleado,
                    nombre_completo,
                    COALESCE(NULLIF(LTRIM(RTRIM(deptop)), ''), departamento_intelisis) AS departamento,
                    categoria,
                    reporta_a,
                    nombre_reporta_a,
                    email_reporta_a,
                    gerente,
                    nombre_gerente,
                    email_gerente,
                    director,
                    nombre_director,
                    email_director
                FROM ni_empleados_maestro
                WHERE numero_empleado = :numero_empleado
            """),
            {"numero_empleado": numero_empleado}
        ).mappings().first()

        if empleado:
            aplica_he = 1 if str(empleado["categoria"]).strip().upper() == "SINDICALIZADO" else 0

            conn.execute(
                text("""
                    INSERT INTO ni_horas_extra_autorizacion (
                        fecha_operativa,
                        numero_empleado,
                        nombre_completo,
                        departamento,
                        categoria_intelisis,
                        aplica_he,
                        tipo_tiempo_extra_detectado,
                        tipo_tiempo_extra_final,
                        minutos_detectados,
                        minutos_autorizados,
                        minutos_dobles_autorizados,
                        minutos_triples_autorizados,
                        estatus,
                        estatus_autorizacion,
                        origen,
                        motivo,
                        creado_por,
                        fecha_creacion,
                        supervisor_numero,
                        supervisor_nombre,
                        supervisor_email,
                        gerente_numero,
                        gerente_nombre,
                        gerente_email,
                        director_numero,
                        director_nombre,
                        director_email,
                        nivel_autorizacion_requerido
                    )
                    VALUES (
                        :fecha_operativa,
                        :numero_empleado,
                        :nombre_completo,
                        :departamento,
                        :categoria_intelisis,
                        :aplica_he,
                        NULL,
                        :tipo_tiempo_extra_final,
                        0,
                        :minutos_autorizados,
                        0,
                        0,
                        CASE WHEN :aplica_he = 1 THEN 'AGREGADA_MANUAL' ELSE 'NO_CONSIDERAR' END,
                        CASE WHEN :aplica_he = 1 THEN 'PENDIENTE_AUTORIZACION' ELSE 'NO_APLICA' END,
                        'MANUAL',
                        :motivo,
                        'usuario_actual',
                        GETDATE(),
                        :supervisor_numero,
                        :supervisor_nombre,
                        :supervisor_email,
                        :gerente_numero,
                        :gerente_nombre,
                        :gerente_email,
                        :director_numero,
                        :director_nombre,
                        :director_email,
                        CASE
                            WHEN :tipo_tiempo_extra_final = 'HE_DESCANSO' THEN 'GERENTE'
                            WHEN :minutos_autorizados >= 480 THEN 'DIRECTOR'
                            WHEN :minutos_autorizados >= 180 THEN 'GERENTE'
                            ELSE 'SUPERVISOR'
                        END
                    )
                """),
                {
                    "fecha_operativa": fecha_operativa,
                    "numero_empleado": empleado["numero_empleado"],
                    "nombre_completo": empleado["nombre_completo"],
                    "departamento": empleado["departamento"],
                    "categoria_intelisis": empleado["categoria"],
                    "aplica_he": aplica_he,
                    "tipo_tiempo_extra_final": tipo_tiempo_extra_final,
                    "minutos_autorizados": minutos,
                    "motivo": motivo,
                    "supervisor_numero": empleado["reporta_a"],
                    "supervisor_nombre": empleado["nombre_reporta_a"],
                    "supervisor_email": empleado["email_reporta_a"],
                    "gerente_numero": empleado["gerente"],
                    "gerente_nombre": empleado["nombre_gerente"],
                    "gerente_email": empleado["email_gerente"],
                    "director_numero": empleado["director"],
                    "director_nombre": empleado["nombre_director"],
                    "director_email": empleado["email_director"],
                }
            )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento_filtro:
        url += f"&departamento={departamento_filtro}"

    return RedirectResponse(url=url, status_code=303)


@router.get("/horas-extra/detalle-jornada", response_class=HTMLResponse)
def detalle_jornada_he(
    request: Request,
    numero_empleado: str,
    fecha: str,
):
    with engine.begin() as conn:
        jornada = conn.execute(
            text("""
                SELECT TOP 1
                    id,
                    fecha_operativa,
                    numero_empleado,
                    nombre_completo,
                    departamento,
                    entrada_esperada,
                    salida_esperada,
                    checada_entrada_valida,
                    checada_salida_valida,
                    primera_checada,
                    ultima_checada,
                    total_checadas,
                    estatus_dia,
                    minutos_retardo,
                    minutos_extra_detectados,
                    tipo_tiempo_extra,
                    observaciones
                FROM ni_jornada_diaria
                WHERE numero_empleado = :numero_empleado
                  AND fecha_operativa = :fecha
                ORDER BY id DESC
            """),
            {
                "numero_empleado": numero_empleado,
                "fecha": fecha
            }
        ).mappings().first()

        checadas = conn.execute(
            text("""
                SELECT
                    punch_time,
                    punch_state,
                    terminal_alias,
                    area_alias,
                    source,
                    verify_type
                FROM ni_checadas_raw
                WHERE numero_empleado = :numero_empleado
                  AND CAST(punch_time AS DATE) = :fecha
                ORDER BY punch_time
            """),
            {
                "numero_empleado": numero_empleado,
                "fecha": fecha
            }
        ).mappings().all()

        he = conn.execute(
            text("""
                SELECT
                    id,
                    tipo_tiempo_extra_final,
                    CAST(ISNULL(minutos_detectados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
                    CAST(ISNULL(minutos_autorizados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas,
                    estatus,
                    estatus_autorizacion,
                    motivo,
                    observaciones
                FROM ni_horas_extra_autorizacion
                WHERE numero_empleado = :numero_empleado
                  AND fecha_operativa = :fecha
                  AND estatus NOT IN ('CANCELADO')
                ORDER BY id
            """),
            {
                "numero_empleado": numero_empleado,
                "fecha": fecha
            }
        ).mappings().all()

    return templates.TemplateResponse(
        request=request,
        name="he_detalle_jornada.html",
        context={
            "jornada": {k: _serialize_value(v) for k, v in dict(jornada).items()} if jornada else None,
            "checadas": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in checadas
            ],
            "he": [
                {k: _serialize_value(v) for k, v in dict(row).items()}
                for row in he
            ],
            "numero_empleado": numero_empleado,
            "fecha": fecha,
        }
    )

@router.get("/horas-extra/empleado")
def empleado_semanal(
    request: Request,
    numero_empleado: str,
    fecha_inicio: str,
    fecha_fin: str,
):
    fi_date = date.fromisoformat(fecha_inicio)
    ff_date = date.fromisoformat(fecha_fin)
    
    # Mapeo de días de la semana
    dias_nombres = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
    
    dias_periodo = []
    d = fi_date
    while d <= ff_date:
        dias_periodo.append({
            "fecha": d.isoformat(),
            "dia": dias_nombres[d.weekday()],
            "label": f"{d.day:02d}",
            "numero_dia": d.day
        })
        d += timedelta(days=1)

    with engine.begin() as conn:
        # Información general del empleado
        empleado = conn.execute(
            text("""
                SELECT TOP 1
                    numero_empleado,
                    nombre_completo,
                    COALESCE(NULLIF(LTRIM(RTRIM(deptop)), ''), departamento_intelisis) AS departamento,
                    categoria,
                    email_reporta_a
                FROM ni_empleados_maestro
                WHERE numero_empleado = :numero_empleado
            """),
            {"numero_empleado": numero_empleado}
        ).mappings().first()

        # Detalle HE por día para este empleado
        he_diaria = conn.execute(
            text("""
                SELECT
                    fecha_operativa,
                    tipo_tiempo_extra_final,
                    CAST(ISNULL(minutos_detectados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
                    CAST(ISNULL(minutos_autorizados, 0) / 60.0 AS DECIMAL(10,2)) AS horas_autorizadas,
                    estatus,
                    estatus_autorizacion,
                    revisor_nombre,
                    autorizador_nombre,
                    notificador_nombre,
                    flujo_autorizacion,
                    motivo,
                    observaciones
                FROM ni_horas_extra_autorizacion
                WHERE numero_empleado = :numero_empleado
                  AND fecha_operativa BETWEEN :fecha_inicio AND :fecha_fin
                  AND ISNULL(aplica_he, 0) = 1
                ORDER BY fecha_operativa
            """),
            {
                "numero_empleado": numero_empleado,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            }
        ).mappings().all()

        # Crear mapa de HE por fecha
        he_map = {}
        for he in he_diaria:
            fecha = he.fecha_operativa
            if fecha not in he_map:
                he_map[fecha] = []
            he_map[fecha].append(he)

        # Checadas diarias para matriz visual
        checadas_por_dia = conn.execute(
            text("""
                SELECT
                    CAST(punch_time AS DATE) AS fecha,
                    COUNT(*) AS total_checadas,
                    MIN(punch_time) AS primera_checada,
                    MAX(punch_time) AS ultima_checada
                FROM ni_checadas_raw
                WHERE numero_empleado = :numero_empleado
                  AND CAST(punch_time AS DATE) BETWEEN :fecha_inicio AND :fecha_fin
                GROUP BY CAST(punch_time AS DATE)
            """),
            {
                "numero_empleado": numero_empleado,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin
            }
        ).mappings().all()

        checadas_map = {}
        for c in checadas_por_dia:
            checadas_map[c.fecha.isoformat()] = {k: _serialize_value(v) for k, v in dict(c).items()}

        # Serializar he_map
        he_map_serialized = {}
        for fecha, he_list in he_map.items():
            he_map_serialized[fecha] = [
                {k: _serialize_value(v) for k, v in dict(he).items()}
                for he in he_list
            ]

    return templates.TemplateResponse(
        request=request,
        name="he_empleado_semanal.html",
        context={
            "numero_empleado": numero_empleado,
            "empleado": {k: _serialize_value(v) for k, v in dict(empleado).items()} if empleado else None,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "dias_periodo": dias_periodo,
            "he_map": he_map_serialized,
            "checadas_map": checadas_map,
        }
    )

@router.post("/horas-extra/confirmar-seleccionados")
def confirmar_seleccionados(
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    empleados: list[str] = Form(...),
    departamento: str | None = Form(None),
):
    empleados_csv = ",".join(empleados)

    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_confirmar_empleados_semana
                    @fecha_inicio = :fecha_inicio,
                    @fecha_fin = :fecha_fin,
                    @empleados_csv = :empleados_csv,
                    @usuario = :usuario
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "empleados_csv": empleados_csv,
                "usuario": "usuario_actual"
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"
    return RedirectResponse(url=url, status_code=303)

@router.post("/horas-extra/no-considerar-seleccionados")
def no_considerar_seleccionados(
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    empleados: list[str] = Form(...),
    motivo: str = Form("No considerado por supervisor"),
    departamento: str | None = Form(None),
):
    empleados_csv = ",".join(empleados)

    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_no_considerar_empleados_semana
                    @fecha_inicio = :fecha_inicio,
                    @fecha_fin = :fecha_fin,
                    @empleados_csv = :empleados_csv,
                    @motivo = :motivo,
                    @usuario = :usuario
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "empleados_csv": empleados_csv,
                "motivo": motivo,
                "usuario": "usuario_actual"
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"
    return RedirectResponse(url=url, status_code=303)
def confirmar_seleccionados(
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    empleados: list[str] = Form(...),
    departamento: str | None = Form(None),
):
    empleados_csv = ",".join(empleados)

    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_confirmar_empleados_semana
                    @fecha_inicio = :fecha_inicio,
                    @fecha_fin = :fecha_fin,
                    @empleados_csv = :empleados_csv,
                    @usuario = :usuario
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "empleados_csv": empleados_csv,
                "usuario": "usuario_actual"
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"
    return RedirectResponse(url=url, status_code=303)

@router.post("/horas-extra/no-considerar-seleccionados")
def no_considerar_seleccionados(
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    empleados: list[str] = Form(...),
    motivo: str = Form("No considerado por supervisor"),
    departamento: str | None = Form(None),
):
    empleados_csv = ",".join(empleados)

    with engine.begin() as conn:
        conn.execute(
            text("""
                EXEC sp_ni_he_no_considerar_empleados_semana
                    @fecha_inicio = :fecha_inicio,
                    @fecha_fin = :fecha_fin,
                    @empleados_csv = :empleados_csv,
                    @motivo = :motivo,
                    @usuario = :usuario
            """),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "empleados_csv": empleados_csv,
                "motivo": motivo,
                "usuario": "usuario_actual"
            }
        )

    url = f"/horas-extra?fecha_inicio={fecha_inicio}&fecha_fin={fecha_fin}"
    if departamento:
        url += f"&departamento={departamento}"
    return RedirectResponse(url=url, status_code=303)
