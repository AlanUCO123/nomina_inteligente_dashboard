from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import RedirectResponse
from datetime import datetime, date, timedelta
from app.intelisis_database import intelisis_fetch_one
from app.portalwyny_database import (
    portal_fetch_one,
    portal_fetch_all,
)


router = APIRouter()

templates = None


def set_templates(templates_instance):
    global templates
    templates = templates_instance


@router.get("/solicitudes/prueba")
def solicitudes_prueba(request: Request):

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    numero_empleado = str(
        numero_empleado or ""
    ).strip()

    if not numero_empleado:
        return {
            "ok": False,
            "mensaje": (
                "El usuario de NOVA no tiene "
                "numero_empleado en la sesión."
            ),
        }

    usuario_portal = portal_fetch_one(
        """
        SELECT TOP 1
            ID_PROCESS,
            ID_ESTATUS,
            idUsuarioFk,
            LTRIM(RTRIM(numeroEmpleado)) AS numeroEmpleado,
            nombreCompleto
        FROM dbo.usuarioEmpleado
        WHERE
            LTRIM(RTRIM(numeroEmpleado))
                = :numero_empleado
        ORDER BY ID_PROCESS DESC
        """,
        {
            "numero_empleado": numero_empleado,
        },
    )

    resumen = portal_fetch_one(
        """
        SELECT
            SUM(
                CASE
                    WHEN ID_ESTATUS = 21
                    THEN 1
                    ELSE 0
                END
            ) AS pendientes,

            SUM(
                CASE
                    WHEN ID_ESTATUS = 23
                    THEN 1
                    ELSE 0
                END
            ) AS autorizados,

            SUM(
                CASE
                    WHEN ID_ESTATUS = 24
                    THEN 1
                    ELSE 0
                END
            ) AS rechazados

        FROM dbo.empleadosSolicitudes

        WHERE
            LTRIM(RTRIM(idEmpleado))
                = :numero_empleado
        """,
        {
            "numero_empleado": numero_empleado,
        },
    )

    return {
        "ok": True,

        "nova": {
            "usuario_id": usuario_id,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,
        },

        "portal_wyny": usuario_portal,

        "solicitudes": {
            "pendientes": (
                int(resumen["pendientes"] or 0)
                if resumen
                else 0
            ),

            "autorizados": (
                int(resumen["autorizados"] or 0)
                if resumen
                else 0
            ),

            "rechazados": (
                int(resumen["rechazados"] or 0)
                if resumen
                else 0
            ),
        },
    }

# ============================================================
# MIS VACACIONES Y PERMISOS
# SOLO LECTURA
# ============================================================

ESTADOS_SOLICITUD = {
    "PENDIENTES": 21,
    "AUTORIZADOS": 23,
    "RECHAZADOS": 24,
}

MESES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def formatear_fecha_hora(valor):
    """
    Convierte:
        2026-08-12T11:40:57.720000

    en:
        12 Ago 2026 · 11:40
    """

    if not valor:
        return ""

    try:

        if isinstance(valor, datetime):
            fecha = valor

        else:
            fecha = datetime.fromisoformat(
                str(valor)
            )

        return (
            f"{fecha.day:02d} "
            f"{MESES_ES[fecha.month]} "
            f"{fecha.year} · "
            f"{fecha.strftime('%H:%M')}"
        )

    except (ValueError, TypeError):
        return str(valor)

@router.get("/solicitudes")
def solicitudes_inicio(
    request: Request,
    estado: str = Query("PENDIENTES"),
):

    # --------------------------------------------------------
    # Sesión NOVA
    # --------------------------------------------------------

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    numero_empleado = str(
        numero_empleado or ""
    ).strip()

    if not numero_empleado:
        return templates.TemplateResponse(
            "solicitudes.html",
            {
                "request": request,
                "login_user": login_user,
                "nombre_usuario": nombre_usuario,
                "numero_empleado": numero_empleado,
                "roles": roles,

                "usuario_portal": None,
                "solicitudes": [],
                "estado": "PENDIENTES",

                "resumen": {
                    "pendientes": 0,
                    "autorizados": 0,
                    "rechazados": 0,
                },

                "error": (
                    "Tu usuario de NOVA no tiene número "
                    "de empleado relacionado."
                ),
            },
        )

    # --------------------------------------------------------
    # Estado seleccionado
    # --------------------------------------------------------

    estado = str(
        estado or "PENDIENTES"
    ).strip().upper()

    if estado not in ESTADOS_SOLICITUD:
        estado = "PENDIENTES"

    id_estatus = ESTADOS_SOLICITUD[estado]

    # --------------------------------------------------------
    # Usuario correspondiente en portalWyny
    # --------------------------------------------------------

    usuario_portal = portal_fetch_one(
        """
        SELECT TOP 1
            ID_PROCESS,
            ID_ESTATUS,
            idUsuarioFk,
            LTRIM(RTRIM(numeroEmpleado)) AS numeroEmpleado,
            nombreCompleto

        FROM dbo.usuarioEmpleado

        WHERE
            LTRIM(RTRIM(numeroEmpleado))
                = :numero_empleado

        ORDER BY ID_PROCESS DESC
        """,
        {
            "numero_empleado": numero_empleado,
        },
    )

    # --------------------------------------------------------
    # Contadores
    # --------------------------------------------------------

    resumen_raw = portal_fetch_one(
        """
        SELECT
            SUM(
                CASE
                    WHEN ID_ESTATUS = 21
                    THEN 1
                    ELSE 0
                END
            ) AS pendientes,

            SUM(
                CASE
                    WHEN ID_ESTATUS = 23
                    THEN 1
                    ELSE 0
                END
            ) AS autorizados,

            SUM(
                CASE
                    WHEN ID_ESTATUS = 24
                    THEN 1
                    ELSE 0
                END
            ) AS rechazados

        FROM dbo.empleadosSolicitudes

        WHERE
            LTRIM(RTRIM(idEmpleado))
                = :numero_empleado
        """,
        {
            "numero_empleado": numero_empleado,
        },
    ) or {}

    resumen = {
        "pendientes": int(
            resumen_raw.get("pendientes") or 0
        ),
        "autorizados": int(
            resumen_raw.get("autorizados") or 0
        ),
        "rechazados": int(
            resumen_raw.get("rechazados") or 0
        ),
    }

    # --------------------------------------------------------
    # Solicitudes del estado seleccionado
    # --------------------------------------------------------

    solicitudes = portal_fetch_all(
        """
        SELECT TOP 100

            es.ID_PROCESS,
            es.ID_ESTATUS,
            es.idTipoPermisoFk,

            CASE

                WHEN es.idTipoPermisoFk = 1
                    THEN 'Vacaciones'

                WHEN es.idTipoPermisoFk = 2
                    THEN 'Permiso con goce de sueldo'

                WHEN es.idTipoPermisoFk = 3
                    THEN 'Permiso sin goce de sueldo'

                ELSE ISNULL(
                    tp.permisoNombre,
                    'Solicitud'
                )

            END AS permiso_nombre,

            CASE

                WHEN es.idTipoPermisoFk = 1
                    THEN 'VACACIONES'

                WHEN es.idTipoPermisoFk BETWEEN 2 AND 3
                    THEN 'PERMISO_COMPLETO'

                ELSE 'PERMISO_PARCIAL'

            END AS grupo_solicitud,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,
            es.fechaConfirmacion,

            es.diasTotales,
            es.diasHabiles,

            es.horaInicio,
            es.horaFinal,

            CAST(es.motivoPermiso AS varchar(max))
                AS motivoPermiso,

            CAST(es.motivoRechazo AS varchar(max))
                AS motivoRechazo,

            es.tipoPermisoOtrosDesc,
            es.conGoce,
            es.esLaboral

        FROM dbo.empleadosSolicitudes es

        LEFT JOIN dbo.tiposPermisos tp
            ON tp.ID_PROCESS = es.idTipoPermisoFk

        WHERE
            LTRIM(RTRIM(es.idEmpleado))
                = :numero_empleado

            AND es.ID_ESTATUS
                = :id_estatus

        ORDER BY
            es.fechaSolicitud DESC,
            es.ID_PROCESS DESC
        """,
        {
            "numero_empleado": numero_empleado,
            "id_estatus": id_estatus,
        },
    )

    for solicitud in solicitudes:

        solicitud["fechaSolicitud_formateada"] = (
            formatear_fecha_hora(
                solicitud.get("fechaSolicitud")
            )
        )

        solicitud["fechaConfirmacion_formateada"] = (
            formatear_fecha_hora(
                solicitud.get("fechaConfirmacion")
            )
        )

    return templates.TemplateResponse(
        "solicitudes.html",
        {
            "request": request,

            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado,
            "roles": roles,

            "usuario_portal": usuario_portal,
            "solicitudes": solicitudes,

            "estado": estado,
            "resumen": resumen,

            "error": None,
        },
    )

# ============================================================
# SOLICITAR VACACIONES
# MODO VALIDACIÓN - NO GUARDA NADA
# ============================================================

def _obtener_empleado_portal(numero_empleado: str):

    return portal_fetch_one(
        """
        SELECT TOP 1
            ID_PROCESS,
            ID_ESTATUS,
            idUsuarioFk,
            LTRIM(RTRIM(numeroEmpleado)) AS numeroEmpleado,
            nombreCompleto

        FROM dbo.usuarioEmpleado

        WHERE
            LTRIM(RTRIM(numeroEmpleado))
                = :numero_empleado

        ORDER BY
            ID_PROCESS DESC
        """,
        {
            "numero_empleado": numero_empleado,
        },
    )

# ============================================================
# RESUMEN REAL DE VACACIONES
# INTELISIS + PORTAL WYNY
# SOLO LECTURA
# ============================================================

def _to_float_safe(value, default=0.0):

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _numero_limpio(value):

    numero = _to_float_safe(value)

    if numero.is_integer():
        return int(numero)

    return round(numero, 2)


def _parse_fecha_iso(value):

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return datetime.fromisoformat(
            str(value)
        ).date()

    except (TypeError, ValueError):
        return None


def _datos_aniversario(fecha_antiguedad):

    fecha_base = _parse_fecha_iso(
        fecha_antiguedad
    )

    if not fecha_base:
        return {
            "fecha": "-",
            "anios": "-",
        }

    hoy = date.today()

    # El Portal WYNY muestra la antigüedad como:
    # días transcurridos / 365
    antiguedad = round(
        (hoy - fecha_base).days / 365.0,
        2,
    )

    # Aniversario del año actual
    try:

        aniversario = fecha_base.replace(
            year=hoy.year
        )

    except ValueError:
        # Caso 29 de febrero en año no bisiesto
        aniversario = date(
            hoy.year,
            2,
            28,
        )

    return {
        "fecha":
            aniversario.strftime("%d-%m-%Y"),

        "anios":
            f"{antiguedad:.2f}",
    }

def _dias_vacaciones_anuales(
    anios_completos: int,
):
    """
    Días anuales que corresponden al ciclo actual.

    1 = 12
    2 = 14
    3 = 16
    4 = 18
    5 = 20
    6-10 = 22
    11-15 = 24
    16-20 = 26
    21-25 = 28
    etc.
    """

    anios = max(
        1,
        int(anios_completos or 0),
    )

    if anios <= 5:
        return 10 + (anios * 2)

    bloque = (
        (anios - 6) // 5
    )

    return 22 + (bloque * 2)


def _ultimo_aniversario(
    fecha_antiguedad: date,
    hoy: date,
):

    try:

        aniversario = fecha_antiguedad.replace(
            year=hoy.year
        )

    except ValueError:

        aniversario = date(
            hoy.year,
            2,
            28,
        )


    if aniversario > hoy:

        try:

            aniversario = fecha_antiguedad.replace(
                year=hoy.year - 1
            )

        except ValueError:

            aniversario = date(
                hoy.year - 1,
                2,
                28,
            )


    return aniversario


def _calcular_acumulado_proporcional(
    fecha_antiguedad,
):

    fecha_base = _parse_fecha_iso(
        fecha_antiguedad
    )

    if not fecha_base:

        return {
            "dias": 0,
            "dias_anuales": 0,
            "dias_transcurridos": 0,
            "anios_completos": 0,
        }


    hoy = date.today()

    aniversario = _ultimo_aniversario(
        fecha_base,
        hoy,
    )


    anios_completos = (
        aniversario.year
        - fecha_base.year
    )


    dias_anuales = _dias_vacaciones_anuales(
        anios_completos
    )


    dias_transcurridos = (
        hoy - aniversario
    ).days


    proporcional = (
        dias_anuales
        * dias_transcurridos
        / 365.0
    )


    # Redondeo normal .5 hacia arriba.
    dias_acumulados = int(
        proporcional + 0.5
    )


    return {
        "dias":
            dias_acumulados,

        "dias_anuales":
            dias_anuales,

        "dias_transcurridos":
            dias_transcurridos,

        "anios_completos":
            anios_completos,
    }

def _obtener_resumen_vacaciones(
    numero_empleado: str,
):

    # ========================================================
    # 1. INTELISIS
    # ========================================================

    intelisis = intelisis_fetch_one(
        """
        SELECT TOP 1

            LTRIM(RTRIM(p.Personal))
                AS Personal,

            LTRIM(RTRIM(ISNULL(
                p.Departamento,
                ''
            ))) AS Departamento,

            LTRIM(RTRIM(ISNULL(
                p.ReportaA,
                ''
            ))) AS ReportaA,

            p.FechaAntiguedad,

            LTRIM(RTRIM(
                CONCAT(
                    ISNULL(j.Nombre, ''),
                    ' ',
                    ISNULL(j.ApellidoPaterno, ''),
                    ' ',
                    ISNULL(j.ApellidoMaterno, '')
                )
            )) AS Supervisor,

            TRY_CONVERT(
                float,
                dbo.fnwPerSaldoVacaciones(
                    p.Personal
                )
            ) AS DiasBase

        FROM dbo.Personal p

        LEFT JOIN dbo.Personal j
            ON LTRIM(RTRIM(j.Personal))
             = LTRIM(RTRIM(p.ReportaA))

        WHERE
            LTRIM(RTRIM(p.Personal))
                = :numero_empleado
        """,
        {
            "numero_empleado":
                numero_empleado,
        },
    )


    if not intelisis:
        return None


    # ========================================================
    # 2. DÍAS BASE
    # ========================================================

    dias_base = _to_float_safe(
        intelisis.get(
            "DiasBase"
        )
    )


    # ========================================================
    # 3. ACUMULADO PROPORCIONAL
    #
    # Ejemplos comprobados Portal WYNY:
    #
    # Marisol:
    # 14 + 3 = 17
    #
    # Patricio:
    # 4 + 17 = 21
    #
    # Erika:
    # 27 + 3 = 30
    # ========================================================

    proporcional = (
        _calcular_acumulado_proporcional(
            intelisis.get(
                "FechaAntiguedad"
            )
        )
    )


    acumulado_extra = _to_float_safe(
        proporcional.get(
            "dias"
        )
    )


    total_disponibles = (
        dias_base
        + acumulado_extra
    )


    # ========================================================
    # 4. VACACIONES PROGRAMADAS
    #
    # Autorizadas que todavía tengan días pendientes
    # desde HOY en adelante.
    #
    # Importante:
    # incluye una vacación que comience HOY.
    # ========================================================

    programadas = portal_fetch_all(
        """
        SELECT

            fechaInicio,
            fechaFinal,
            diasHabiles

        FROM dbo.empleadosSolicitudes

        WHERE
            LTRIM(RTRIM(idEmpleado))
                = :numero_empleado

            AND idTipoPermisoFk = 1

            AND ID_ESTATUS = 23

            AND fechaFinal
                >= CONVERT(date, GETDATE())

        ORDER BY
            fechaInicio,
            ID_PROCESS
        """,
        {
            "numero_empleado":
                numero_empleado,
        },
    )


    hoy = date.today()

    dias_programados = 0


    for solicitud in programadas:

        fecha_inicio = _parse_fecha_iso(
            solicitud.get(
                "fechaInicio"
            )
        )

        fecha_final = _parse_fecha_iso(
            solicitud.get(
                "fechaFinal"
            )
        )


        if not fecha_inicio or not fecha_final:
            continue


        # Si la vacación ya comenzó,
        # únicamente contamos lo pendiente
        # desde hoy.
        inicio_conteo = max(
            fecha_inicio,
            hoy,
        )


        if fecha_final < inicio_conteo:
            continue


        dias_programados += (
            _calcular_dias_habiles(
                inicio_conteo,
                fecha_final,
            )
        )


    # ========================================================
    # 5. DÍAS REALES
    #
    # El Portal WYNY muestra como "Reales":
    #
    # Total disponibles + Programados
    # ========================================================

    dias_reales = (
        total_disponibles
        + dias_programados
    )


    # ========================================================
    # 6. ANIVERSARIO
    # ========================================================

    aniversario = _datos_aniversario(
        intelisis.get(
            "FechaAntiguedad"
        )
    )


    base_limpio = _numero_limpio(
        dias_base
    )

    extra_limpio = _numero_limpio(
        acumulado_extra
    )

    total_limpio = _numero_limpio(
        total_disponibles
    )

    programados_limpio = _numero_limpio(
        dias_programados
    )

    reales_limpio = _numero_limpio(
        dias_reales
    )


    acumulado_texto = (
        f"{total_limpio} = "
        f"[{base_limpio} + "
        f"{extra_limpio}]"
    )


    return {

        "departamento":
            intelisis.get(
                "Departamento"
            ) or "-",

        "supervisor":
            intelisis.get(
                "Supervisor"
            ) or "-",

        "fecha_antiguedad":
            intelisis.get(
                "FechaAntiguedad"
            ),

        "aniversario":
            aniversario["fecha"],

        "antiguedad_anios":
            aniversario["anios"],


        # ---------------------------------------------
        # VACACIONES
        # ---------------------------------------------

        "dias_base":
            base_limpio,

        "dias_anuales":
            proporcional.get(
                "dias_anuales"
            ),

        "dias_transcurridos_ciclo":
            proporcional.get(
                "dias_transcurridos"
            ),

        "acumulado_extra":
            extra_limpio,

        "dias_programados":
            programados_limpio,

        "dias_reales":
            reales_limpio,

        "dias_acumulados":
            acumulado_texto,

        "total_disponibles":
            total_limpio,

        "dias_inhabiles":
            "[0,6]",
    }

def _obtener_saldo_vacaciones(numero_empleado: str):

    return portal_fetch_one(
        """
        SELECT TOP 1
            dias_vac,
            Fec_Ini,
            Fec_Fin,
            idProcess,
            idFechaRegistro

        FROM dbo.saldoVacaciones23

        WHERE
            LTRIM(RTRIM(numeroEmpleado))
                = :numero_empleado

        ORDER BY
            idFechaRegistro DESC,
            idProcess DESC
        """,
        {
            "numero_empleado": numero_empleado,
        },
    )


def _contexto_vacaciones(
    request: Request,
    *,
    error=None,
    preview=None,
):

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = str(
        request.session.get("numero_empleado")
        or ""
    ).strip()

    roles = request.session.get("roles", [])

    empleado_portal = None
    vacaciones_resumen = None
    error_vacaciones = None

    if numero_empleado:

        empleado_portal = _obtener_empleado_portal(
            numero_empleado
        )

        try:

            vacaciones_resumen = (
                _obtener_resumen_vacaciones(
                    numero_empleado
                )
            )

        except Exception:

            error_vacaciones = (
                "No fue posible consultar en este "
                "momento la información de vacaciones "
                "de Intelisis."
            )

    return {
        "request": request,

        "usuario_id": usuario_id,
        "login_user": login_user,
        "nombre_usuario": nombre_usuario,
        "numero_empleado": numero_empleado,
        "roles": roles,

        "empleado_portal": empleado_portal,
        "vacaciones_resumen": vacaciones_resumen,
        "error_vacaciones": error_vacaciones,

        "hoy_iso": date.today().isoformat(),

        "error": error,
        "preview": preview,
    }


# ============================================================
# FORMULARIO
# ============================================================

@router.get("/solicitudes/vacaciones/nueva")
def vacaciones_nueva(
    request: Request,
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        "solicitud_vacaciones.html",
        _contexto_vacaciones(request),
    )


# ============================================================
# VALIDAR SOLICITUD
#
# IMPORTANTE:
# ESTE POST NO HACE INSERT.
# SOLAMENTE VALIDA LAS FECHAS.
# ============================================================

def _calcular_dias_habiles(
    fecha_inicio: date,
    fecha_final: date,
):
    """
    Replica la regla visible del Portal WYNY:
    días inhábiles [0,6] = domingo y sábado.

    Por ahora NO considera festivos extraordinarios,
    porque todavía no tenemos localizada una fuente
    2026 confiable para esos días.
    """

    if fecha_final < fecha_inicio:
        return 0

    dias_habiles = 0
    cursor = fecha_inicio

    while cursor <= fecha_final:

        # Python:
        # lunes = 0
        # ...
        # sábado = 5
        # domingo = 6
        if cursor.weekday() < 5:
            dias_habiles += 1

        cursor += timedelta(days=1)

    return dias_habiles

@router.post("/solicitudes/vacaciones/validar")
def vacaciones_validar(
    request: Request,

    fecha_inicio: str = Form(...),
    fecha_final: str = Form(...),
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    numero_empleado = str(
        request.session.get("numero_empleado")
        or ""
    ).strip()

    if not numero_empleado:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error=(
                    "Tu usuario de NOVA no tiene "
                    "número de empleado relacionado."
                ),
            ),
        )

    # --------------------------------------------------------
    # Validar fechas
    # --------------------------------------------------------

    try:

        fecha_inicio_obj = date.fromisoformat(
            fecha_inicio
        )

        fecha_final_obj = date.fromisoformat(
            fecha_final
        )

        hoy = date.today()

        if fecha_inicio_obj < hoy:

            return templates.TemplateResponse(
                "solicitud_vacaciones.html",
                _contexto_vacaciones(
                    request,
                    error=(
                        "No puedes solicitar vacaciones "
                        "en una fecha anterior al día de hoy."
                    ),
                ),
            )


        if fecha_final_obj < hoy:

            return templates.TemplateResponse(
                "solicitud_vacaciones.html",
                _contexto_vacaciones(
                    request,
                    error=(
                        "La fecha final no puede ser "
                        "anterior al día de hoy."
                    ),
                ),
            )

    except ValueError:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error="Las fechas seleccionadas no son válidas.",
            ),
        )

    if fecha_final_obj < fecha_inicio_obj:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error=(
                    "La fecha final no puede ser "
                    "anterior a la fecha inicial."
                ),
            ),
        )

    # --------------------------------------------------------
    # Días naturales
    #
    # NO los llamamos días hábiles porque todavía debemos
    # confirmar la lógica exacta que usaba PortalWyny.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # CALCULAR PERIODO
    # --------------------------------------------------------

    dias_naturales = (
        fecha_final_obj - fecha_inicio_obj
    ).days + 1


    dias_habiles = _calcular_dias_habiles(
        fecha_inicio_obj,
        fecha_final_obj,
    )


    if dias_habiles <= 0:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error=(
                    "El periodo seleccionado no contiene "
                    "días hábiles."
                ),
                preview={
                    "fecha_inicio": fecha_inicio,
                    "fecha_final": fecha_final,
                },
            ),
        )


    # --------------------------------------------------------
    # DISPONIBILIDAD REAL
    # --------------------------------------------------------

    resumen_vacaciones = (
        _obtener_resumen_vacaciones(
            numero_empleado
        )
    )

    if not resumen_vacaciones:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error=(
                    "No fue posible consultar tu saldo "
                    "actual de vacaciones."
                ),
                preview={
                    "fecha_inicio": fecha_inicio,
                    "fecha_final": fecha_final,
                },
            ),
        )


    total_disponibles = _to_float_safe(
        resumen_vacaciones.get(
            "total_disponibles"
        )
    )


    if dias_habiles > total_disponibles:

        return templates.TemplateResponse(
            "solicitud_vacaciones.html",
            _contexto_vacaciones(
                request,
                error=(
                    f"El periodo contiene {dias_habiles} "
                    f"días hábiles, pero solamente tienes "
                    f"{_numero_limpio(total_disponibles)} "
                    f"días disponibles."
                ),
                preview={
                    "fecha_inicio": fecha_inicio,
                    "fecha_final": fecha_final,
                    "dias_naturales": dias_naturales,
                    "dias_habiles": dias_habiles,
                },
            ),
        )

    # --------------------------------------------------------
    # Buscar vacaciones que choquen
    #
    # SOLO pendientes (21) o autorizadas (23)
    # --------------------------------------------------------

    conflictos = portal_fetch_all(
        """
        SELECT
            ID_PROCESS,
            ID_ESTATUS,
            fechaInicio,
            fechaFinal,
            diasTotales,
            diasHabiles,
            fechaSolicitud

        FROM dbo.empleadosSolicitudes

        WHERE
            LTRIM(RTRIM(idEmpleado))
                = :numero_empleado

            AND idTipoPermisoFk = 1

            AND ID_ESTATUS IN (21, 23)

            AND fechaInicio <= :fecha_final

            AND fechaFinal >= :fecha_inicio

        ORDER BY
            fechaInicio DESC,
            ID_PROCESS DESC
        """,
        {
            "numero_empleado":
                numero_empleado,

            "fecha_inicio":
                fecha_inicio,

            "fecha_final":
                fecha_final,
        },
    )

    # --------------------------------------------------------
    # PREVIEW
    #
    # NO SE GUARDA NADA
    # --------------------------------------------------------

    disponibles_despues = (
        total_disponibles - dias_habiles
    )

    preview = {

        "fecha_inicio":
            fecha_inicio,

        "fecha_final":
            fecha_final,

        "dias_naturales":
            dias_naturales,

        "dias_habiles":
            dias_habiles,

        "total_disponibles":
            _numero_limpio(
                total_disponibles
            ),

        "disponibles_despues":
            _numero_limpio(
                disponibles_despues
            ),

        "conflictos":
            conflictos,

        "total_conflictos":
            len(conflictos),

        "periodo_valido":
            len(conflictos) == 0,
    }

    # --------------------------------------------------------
    # MOSTRAR RESULTADO DE VALIDACIÓN DE VACACIONES
    # --------------------------------------------------------

    return templates.TemplateResponse(
        "solicitud_vacaciones.html",
        _contexto_vacaciones(
            request,
            preview=preview,
        ),
    )


# ============================================================
# PERMISOS
# MODO VALIDACIÓN - NO GUARDA NADA
# ============================================================

def _contexto_permiso(
    request: Request,
    *,
    error=None,
    preview=None,
    form_data=None,
    parcial=False,
):

    contexto = _contexto_vacaciones(
        request,
    )

    contexto["error"] = error
    contexto["preview"] = preview
    contexto["form_data"] = form_data or {}

    if parcial:

        contexto["tipos_permiso_parcial"] = portal_fetch_all(
            """
            SELECT
                ID_PROCESS,
                permisoNombre,
                CAST(
                    permisoDescripcion AS varchar(max)
                ) AS permisoDescripcion

            FROM dbo.tiposPermisos

            WHERE
                ID_ESTATUS = 46

                AND ID_PROCESS NOT IN (
                    1,  -- Vacaciones
                    2,  -- Permiso completo con goce
                    3,  -- Permiso completo sin goce
                    8   -- Incapacidad
                )

            ORDER BY
                ID_PROCESS
            """
        )

    else:

        contexto["tipos_permiso_parcial"] = []

    return contexto


# ============================================================
# PERMISO TOTAL
# ============================================================

@router.get("/solicitudes/permiso/nuevo")
def permiso_nuevo(
    request: Request,
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        "solicitud_permiso.html",
        _contexto_permiso(request),
    )


@router.post("/solicitudes/permiso/validar")
def permiso_validar(
    request: Request,

    fecha_inicio: str = Form(...),
    fecha_final: str = Form(...),
    motivo: str = Form(...),
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )


    numero_empleado = str(
        request.session.get("numero_empleado")
        or ""
    ).strip()


    motivo = str(
        motivo or ""
    ).strip()


    form_data = {
        "fecha_inicio": fecha_inicio,
        "fecha_final": fecha_final,
        "motivo": motivo,
    }


    if not numero_empleado:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error=(
                    "Tu usuario de NOVA no tiene "
                    "número de empleado relacionado."
                ),
                form_data=form_data,
            ),
        )


    if not motivo:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error=(
                    "Debes indicar el motivo del permiso."
                ),
                form_data=form_data,
            ),
        )


    # --------------------------------------------------------
    # FECHAS
    # --------------------------------------------------------

    try:

        fecha_inicio_obj = date.fromisoformat(
            fecha_inicio
        )

        fecha_final_obj = date.fromisoformat(
            fecha_final
        )

    except ValueError:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error="Las fechas seleccionadas no son válidas.",
                form_data=form_data,
            ),
        )


    hoy = date.today()


    if fecha_inicio_obj < hoy:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error=(
                    "No puedes solicitar un permiso "
                    "para una fecha anterior al día de hoy."
                ),
                form_data=form_data,
            ),
        )


    if fecha_final_obj < fecha_inicio_obj:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error=(
                    "La fecha final no puede ser "
                    "anterior a la fecha inicial."
                ),
                form_data=form_data,
            ),
        )


    dias_naturales = (
        fecha_final_obj - fecha_inicio_obj
    ).days + 1


    dias_habiles = _calcular_dias_habiles(
        fecha_inicio_obj,
        fecha_final_obj,
    )


    if dias_habiles <= 0:

        return templates.TemplateResponse(
            "solicitud_permiso.html",
            _contexto_permiso(
                request,
                error=(
                    "El periodo seleccionado no contiene "
                    "días hábiles."
                ),
                form_data=form_data,
            ),
        )


    # --------------------------------------------------------
    # CRUCES
    # Pendientes o autorizados
    # --------------------------------------------------------

    conflictos = portal_fetch_all(
        """
        SELECT

            es.ID_PROCESS,
            es.ID_ESTATUS,
            es.idTipoPermisoFk,

            ISNULL(
                tp.permisoNombre,
                'Solicitud'
            ) AS permisoNombre,

            es.fechaInicio,
            es.fechaFinal,

            es.horaInicio,
            es.horaFinal

        FROM dbo.empleadosSolicitudes es

        LEFT JOIN dbo.tiposPermisos tp
            ON tp.ID_PROCESS = es.idTipoPermisoFk

        WHERE
            LTRIM(RTRIM(es.idEmpleado))
                = :numero_empleado

            AND es.ID_ESTATUS IN (21, 23)

            AND es.fechaInicio <= :fecha_final

            AND es.fechaFinal >= :fecha_inicio

        ORDER BY
            es.fechaInicio,
            es.ID_PROCESS
        """,
        {
            "numero_empleado":
                numero_empleado,

            "fecha_inicio":
                fecha_inicio,

            "fecha_final":
                fecha_final,
        },
    )


    preview = {

        "fecha_inicio":
            fecha_inicio,

        "fecha_final":
            fecha_final,

        "dias_naturales":
            dias_naturales,

        "dias_habiles":
            dias_habiles,

        "motivo":
            motivo,

        "conflictos":
            conflictos,

        "total_conflictos":
            len(conflictos),

        "periodo_valido":
            len(conflictos) == 0,
    }


    return templates.TemplateResponse(
        "solicitud_permiso.html",
        _contexto_permiso(
            request,
            preview=preview,
            form_data=form_data,
        ),
    )


# ============================================================
# PERMISO PARCIAL
# ============================================================

@router.get("/solicitudes/permiso-parcial/nuevo")
def permiso_parcial_nuevo(
    request: Request,
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    return templates.TemplateResponse(
        "solicitud_permiso_parcial.html",
        _contexto_permiso(
            request,
            parcial=True,
        ),
    )


@router.post("/solicitudes/permiso-parcial/validar")
def permiso_parcial_validar(
    request: Request,

    tipo_permiso: str = Form(...),

    fecha: str = Form(...),

    hora_inicio: str = Form(...),
    hora_final: str = Form(...),

    motivo: str = Form(...),

    descripcion_otros: str = Form(""),

    confirmar_horario: str | None = Form(None),
):

    if not request.session.get("usuario_id"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )


    numero_empleado = str(
        request.session.get("numero_empleado")
        or ""
    ).strip()


    motivo = str(
        motivo or ""
    ).strip()


    descripcion_otros = str(
        descripcion_otros or ""
    ).strip()


    form_data = {

        "tipo_permiso":
            tipo_permiso,

        "fecha":
            fecha,

        "hora_inicio":
            hora_inicio,

        "hora_final":
            hora_final,

        "motivo":
            motivo,

        "descripcion_otros":
            descripcion_otros,

        "confirmar_horario":
            confirmar_horario,
    }


    if not numero_empleado:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "Tu usuario de NOVA no tiene "
                    "número de empleado relacionado."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    # --------------------------------------------------------
    # TIPO DE PERMISO
    # --------------------------------------------------------

    try:

        tipo_id = int(
            tipo_permiso
        )

    except (TypeError, ValueError):

        tipo_id = 0


    tipos = portal_fetch_all(
        """
        SELECT
            ID_PROCESS,
            permisoNombre

        FROM dbo.tiposPermisos

        WHERE
            ID_ESTATUS = 46

            AND ID_PROCESS NOT IN (
                1,
                2,
                3,
                8
            )
        """
    )


    tipos_validos = {
        int(t["ID_PROCESS"]): t
        for t in tipos
    }


    if tipo_id not in tipos_validos:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "Selecciona un tipo de permiso válido."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    tipo_nombre = (
        tipos_validos[tipo_id]
        .get("permisoNombre")
        or "Permiso parcial"
    )


    # --------------------------------------------------------
    # OTROS
    # --------------------------------------------------------

    if tipo_id == 7 and not descripcion_otros:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "Cuando seleccionas 'Otros' debes "
                    "indicar el tipo de permiso."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    if not motivo:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "Debes indicar el motivo del permiso."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    # --------------------------------------------------------
    # FECHA
    # --------------------------------------------------------

    try:

        fecha_obj = date.fromisoformat(
            fecha
        )

    except ValueError:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "La fecha seleccionada no es válida."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    if fecha_obj < date.today():

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "No puedes solicitar un permiso "
                    "para una fecha anterior al día de hoy."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    # --------------------------------------------------------
    # HORARIO
    # --------------------------------------------------------

    try:

        hora_inicio_obj = datetime.strptime(
            hora_inicio,
            "%H:%M",
        ).time()

        hora_final_obj = datetime.strptime(
            hora_final,
            "%H:%M",
        ).time()

    except ValueError:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "El horario seleccionado no es válido."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    if hora_final_obj <= hora_inicio_obj:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "La hora final debe ser posterior "
                    "a la hora inicial."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    if not confirmar_horario:

        return templates.TemplateResponse(
            "solicitud_permiso_parcial.html",
            _contexto_permiso(
                request,
                error=(
                    "Debes confirmar que revisaste "
                    "el horario de ausencia."
                ),
                form_data=form_data,
                parcial=True,
            ),
        )


    inicio_dt = datetime.combine(
        fecha_obj,
        hora_inicio_obj,
    )

    final_dt = datetime.combine(
        fecha_obj,
        hora_final_obj,
    )


    duracion_minutos = int(
        (
            final_dt - inicio_dt
        ).total_seconds()
        / 60
    )


    horas = (
        duracion_minutos // 60
    )

    minutos = (
        duracion_minutos % 60
    )


    if horas and minutos:

        duracion_texto = (
            f"{horas} h {minutos} min"
        )

    elif horas:

        duracion_texto = (
            f"{horas} h"
        )

    else:

        duracion_texto = (
            f"{minutos} min"
        )


    # --------------------------------------------------------
    # CRUCES
    # --------------------------------------------------------

    conflictos = portal_fetch_all(
        """
        SELECT

            es.ID_PROCESS,
            es.ID_ESTATUS,
            es.idTipoPermisoFk,

            ISNULL(
                tp.permisoNombre,
                'Solicitud'
            ) AS permisoNombre,

            es.fechaInicio,
            es.fechaFinal,

            es.horaInicio,
            es.horaFinal

        FROM dbo.empleadosSolicitudes es

        LEFT JOIN dbo.tiposPermisos tp
            ON tp.ID_PROCESS = es.idTipoPermisoFk

        WHERE
            LTRIM(RTRIM(es.idEmpleado))
                = :numero_empleado

            AND es.ID_ESTATUS IN (21, 23)

            AND es.fechaInicio <= :fecha

            AND es.fechaFinal >= :fecha

            AND (

                es.idTipoPermisoFk IN (
                    1,
                    2,
                    3,
                    8
                )

                OR (

                    es.horaInicio IS NOT NULL

                    AND es.horaFinal IS NOT NULL

                    AND es.horaInicio
                        < CAST(:hora_final AS time)

                    AND es.horaFinal
                        > CAST(:hora_inicio AS time)
                )
            )

        ORDER BY
            es.fechaInicio,
            es.horaInicio,
            es.ID_PROCESS
        """,
        {
            "numero_empleado":
                numero_empleado,

            "fecha":
                fecha,

            "hora_inicio":
                hora_inicio,

            "hora_final":
                hora_final,
        },
    )


    preview = {

        "tipo_id":
            tipo_id,

        "tipo_nombre":
            tipo_nombre,

        "fecha":
            fecha,

        "hora_inicio":
            hora_inicio,

        "hora_final":
            hora_final,

        "duracion_minutos":
            duracion_minutos,

        "duracion_texto":
            duracion_texto,

        "motivo":
            motivo,

        "descripcion_otros":
            descripcion_otros,

        "conflictos":
            conflictos,

        "total_conflictos":
            len(conflictos),

        "periodo_valido":
            len(conflictos) == 0,
    }


    return templates.TemplateResponse(
        "solicitud_permiso_parcial.html",
        _contexto_permiso(
            request,
            preview=preview,
            form_data=form_data,
            parcial=True,
        ),
    )