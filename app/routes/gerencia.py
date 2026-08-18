from datetime import datetime, date

from fastapi import (
    APIRouter,
    Request,
    Form,
    HTTPException,
)
from fastapi.responses import RedirectResponse

from app.database import (
    fetch_all,
    fetch_one,
)

from app.portalwyny_database import (
    portal_fetch_all,
    portal_fetch_one,
)

from app.routes.solicitudes import (
    _obtener_resumen_vacaciones,
)


router = APIRouter(
    prefix="/gerencia",
    tags=["Gerencia"],
)

templates = None


def set_templates(templates_instance):
    global templates
    templates = templates_instance


# ============================================================
# CONSTANTES
# ============================================================

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


# ============================================================
# SESIÓN / SEGURIDAD
# ============================================================

def _contexto_sesion(
    request: Request,
):
    return {
        "usuario_id":
            request.session.get(
                "usuario_id"
            ),

        "login_user":
            request.session.get(
                "login_user"
            ),

        "nombre_usuario":
            request.session.get(
                "nombre_usuario"
            ),

        "numero_empleado":
            str(
                request.session.get(
                    "numero_empleado"
                )
                or ""
            ).strip(),

        "roles":
            request.session.get(
                "roles",
                [],
            ),
    }


def _validar_acceso_gerente(
    request: Request,
):
    contexto = _contexto_sesion(
        request
    )

    if not contexto["usuario_id"]:
        return (
            contexto,
            RedirectResponse(
                url="/login",
                status_code=303,
            ),
        )

    if (
        "GERENTE"
        not in contexto["roles"]
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Este módulo está disponible "
                "únicamente para gerentes."
            ),
        )

    if not contexto["numero_empleado"]:
        raise HTTPException(
            status_code=403,
            detail=(
                "La sesión no tiene un número "
                "de empleado asociado."
            ),
        )

    return contexto, None


# ============================================================
# FORMATOS
# ============================================================

def _parse_fecha(
    valor,
):
    if not valor:
        return None

    if isinstance(
        valor,
        datetime,
    ):
        return valor

    if isinstance(
        valor,
        date,
    ):
        return datetime.combine(
            valor,
            datetime.min.time(),
        )

    texto = str(
        valor
    ).strip()

    try:
        return datetime.fromisoformat(
            texto
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


def _fecha_corta(
    valor,
):
    fecha = _parse_fecha(
        valor
    )

    if not fecha:
        return "—"

    return (
        f"{fecha.day:02d} "
        f"{MESES_ES[fecha.month]} "
        f"{fecha.year}"
    )


def _fecha_hora(
    valor,
):
    fecha = _parse_fecha(
        valor
    )

    if not fecha:
        return "—"

    return (
        f"{fecha.day:02d} "
        f"{MESES_ES[fecha.month]} "
        f"{fecha.year} · "
        f"{fecha.strftime('%H:%M')}"
    )


def _hace_cuanto(
    valor,
):
    fecha = _parse_fecha(
        valor
    )

    if not fecha:
        return ""

    diferencia = (
        date.today()
        - fecha.date()
    ).days

    if diferencia <= 0:
        return "Hoy"

    if diferencia == 1:
        return "Hace 1 día"

    return (
        f"Hace {diferencia} días"
    )


def _hora_corta(
    valor,
):
    if not valor:
        return None

    texto = str(
        valor
    ).strip()

    if len(texto) >= 5:
        return texto[:5]

    return texto


def _tipo_solicitud(
    id_tipo,
):
    try:
        id_tipo = int(
            id_tipo
        )
    except (
        TypeError,
        ValueError,
    ):
        id_tipo = 0

    if id_tipo == 1:
        return {
            "codigo": "VACACIONES",
            "nombre": "Vacaciones",
            "icono": "🏖️",
        }

    if id_tipo in (
        2,
        3,
    ):
        return {
            "codigo":
                "PERMISO_TOTAL",

            "nombre":
                "Permiso",

            "icono":
                "📅",
        }

    return {
        "codigo":
            "PERMISO_PARCIAL",

        "nombre":
            "Permiso parcial",

        "icono":
            "🕒",
    }


# ============================================================
# JERARQUÍA DEL GERENTE
# SOLO LECTURA ✅
# ============================================================

def _equipo_gerente(
    numero_gerente: str,
):
    return fetch_all(
        """
        SELECT
            CAST(
                numero_empleado
                AS varchar(50)
            ) AS numero_empleado,

            nombre_completo,

            COALESCE(
                NULLIF(
                    LTRIM(RTRIM(deptop)),
                    ''
                ),
                departamento_intelisis
            ) AS area_actual,

            departamento_intelisis,

            categoria,

            reporta_a,
            nombre_reporta_a,

            gerente,
            nombre_gerente

        FROM dbo.ni_empleados_maestro

        WHERE
            CAST(
                gerente
                AS varchar(50)
            ) = :numero_gerente

            AND ISNULL(
                activo_intelisis,
                1
            ) = 1

        ORDER BY
            nombre_completo
        """,
        {
            "numero_gerente":
                numero_gerente,
        },
    )


def _mapa_equipo(
    numero_gerente: str,
):
    filas = _equipo_gerente(
        numero_gerente
    )

    return {
        str(
            fila.get(
                "numero_empleado"
            )
            or ""
        ).strip():
            fila

        for fila in filas
    }


def _empleados_por_numeros(
    numeros,
):
    numeros = sorted(
        {
            str(
                numero
                or ""
            ).strip()

            for numero in numeros

            if str(
                numero
                or ""
            ).strip()
        }
    )

    if not numeros:
        return {}

    placeholders = []
    parametros = {}

    for indice, numero in enumerate(
        numeros
    ):
        clave = f"n{indice}"

        placeholders.append(
            f":{clave}"
        )

        parametros[clave] = numero

    sql = f"""
        SELECT
            CAST(
                numero_empleado
                AS varchar(50)
            ) AS numero_empleado,

            nombre_completo,

            COALESCE(
                NULLIF(
                    LTRIM(RTRIM(deptop)),
                    ''
                ),
                departamento_intelisis
            ) AS area_actual,

            departamento_intelisis,

            categoria

        FROM dbo.ni_empleados_maestro

        WHERE
            CAST(
                numero_empleado
                AS varchar(50)
            )
            IN (
                {", ".join(placeholders)}
            )
    """

    filas = fetch_all(
        sql,
        parametros,
    )

    return {
        str(
            fila.get(
                "numero_empleado"
            )
            or ""
        ).strip():
            fila

        for fila in filas
    }


# ============================================================
# AUTORIZAR PERMISOS
# SOLO LECTURA ✅
# ============================================================

def _solicitudes_pendientes_gerente(
    numero_gerente: str,
):
    equipo = _mapa_equipo(
        numero_gerente
    )

    if not equipo:
        return []

    # IMPORTANTE:
    # solamente SELECT.
    filas = portal_fetch_all(
        """
        SELECT
            es.ID_PROCESS,
            es.ID_ESTATUS,

            es.idUsuarioFk,
            es.idEmpleado,
            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,

            es.motivoPermiso,

            es.diasTotales,
            es.diasHabiles,

            es.horaInicio,
            es.horaFinal,

            es.tipoPermisoOtrosDesc,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM dbo.empleadosSolicitudes es

        LEFT JOIN dbo.usuarioEmpleado ue
            ON ue.idUsuarioFk
             = es.idUsuarioFk

        LEFT JOIN dbo.tiposPermisos tp
            ON tp.ID_PROCESS
             = es.idTipoPermisoFk

        WHERE
            es.ID_ESTATUS = 21

            AND es.fechaInicio >= DATEFROMPARTS(
                YEAR(GETDATE()),
                1,
                1
            )

            AND es.fechaInicio < DATEFROMPARTS(
                YEAR(GETDATE()) + 1,
                1,
                1
            )

        ORDER BY
            es.fechaSolicitud DESC,
            es.ID_PROCESS DESC
        """
    )

    resultado = []

    for fila in filas:

        numero = str(
            fila.get(
                "idEmpleado"
            )
            or ""
        ).strip()

        empleado = equipo.get(
            numero
        )

        if not empleado:
            continue

        tipo = _tipo_solicitud(
            fila.get(
                "idTipoPermisoFk"
            )
        )

        preparada = dict(
            fila
        )

        preparada.update({
            "numero_empleado":
                numero,

            "nombre_empleado":
                empleado.get(
                    "nombre_completo"
                )
                or fila.get(
                    "nombreCompleto"
                )
                or numero,

            "departamento":
                empleado.get(
                    "departamento_intelisis"
                )
                or "—",

            "tipo_codigo":
                tipo["codigo"],

            "tipo_nombre":
                tipo["nombre"],

            "tipo_icono":
                tipo["icono"],

            "fecha_inicio_texto":
                _fecha_corta(
                    fila.get(
                        "fechaInicio"
                    )
                ),

            "fecha_final_texto":
                _fecha_corta(
                    fila.get(
                        "fechaFinal"
                    )
                ),

            "fecha_solicitud_texto":
                _fecha_hora(
                    fila.get(
                        "fechaSolicitud"
                    )
                ),

            "hace":
                _hace_cuanto(
                    fila.get(
                        "fechaSolicitud"
                    )
                ),

            "hora_inicio_texto":
                _hora_corta(
                    fila.get(
                        "horaInicio"
                    )
                ),

            "hora_final_texto":
                _hora_corta(
                    fila.get(
                        "horaFinal"
                    )
                ),
        })

        resultado.append(
            preparada
        )

    return resultado


def _solicitud_pendiente_detalle(
    id_process: int,
    numero_gerente: str,
):
    fila = portal_fetch_one(
        """
        SELECT
            es.ID_PROCESS,
            es.ID_ESTATUS,

            es.idUsuarioFk,
            es.idEmpleado,
            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,

            es.motivoPermiso,
            es.motivoRechazo,

            es.diasTotales,
            es.diasHabiles,

            es.horaInicio,
            es.horaFinal,

            es.tipoPermisoOtrosDesc,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM dbo.empleadosSolicitudes es

        LEFT JOIN dbo.usuarioEmpleado ue
            ON ue.idUsuarioFk
             = es.idUsuarioFk

        LEFT JOIN dbo.tiposPermisos tp
            ON tp.ID_PROCESS
             = es.idTipoPermisoFk

        WHERE
            es.ID_PROCESS
                = :id_process

            AND es.ID_ESTATUS = 21
        """,
        {
            "id_process":
                id_process,
        },
    )

    if not fila:
        return None

    numero = str(
        fila.get(
            "idEmpleado"
        )
        or ""
    ).strip()

    equipo = _mapa_equipo(
        numero_gerente
    )

    empleado = equipo.get(
        numero
    )

    # Seguridad:
    # aunque alguien escriba manualmente otro ID
    # en la URL, no puede consultar una solicitud
    # fuera de su gerencia.
    if not empleado:
        return None

    tipo = _tipo_solicitud(
        fila.get(
            "idTipoPermisoFk"
        )
    )

    detalle = dict(
        fila
    )

    detalle.update({
        "numero_empleado":
            numero,

        "nombre_empleado":
            empleado.get(
                "nombre_completo"
            )
            or fila.get(
                "nombreCompleto"
            )
            or numero,

        "departamento":
            empleado.get(
                "departamento_intelisis"
            )
            or "—",

        "categoria":
            empleado.get(
                "categoria"
            )
            or "—",

        "tipo_codigo":
            tipo["codigo"],

        "tipo_nombre":
            tipo["nombre"],

        "tipo_icono":
            tipo["icono"],

        "fecha_inicio_texto":
            _fecha_corta(
                fila.get(
                    "fechaInicio"
                )
            ),

        "fecha_final_texto":
            _fecha_corta(
                fila.get(
                    "fechaFinal"
                )
            ),

        "fecha_solicitud_texto":
            _fecha_hora(
                fila.get(
                    "fechaSolicitud"
                )
            ),

        "hora_inicio_texto":
            _hora_corta(
                fila.get(
                    "horaInicio"
                )
            ),

        "hora_final_texto":
            _hora_corta(
                fila.get(
                    "horaFinal"
                )
            ),
    })

    # Reutilizamos el cálculo de vacaciones
    # que ya dejamos cuadrado contra Portal WYNY.
    try:
        resumen_vacaciones = (
            _obtener_resumen_vacaciones(
                numero
            )
        )

    except Exception:
        resumen_vacaciones = None

    detalle[
        "resumen_vacaciones"
    ] = resumen_vacaciones

    return detalle


@router.get(
    "/permisos"
)
def gerencia_permisos(
    request: Request,
):
    contexto, respuesta = (
        _validar_acceso_gerente(
            request
        )
    )

    if respuesta:
        return respuesta

    solicitudes = (
        _solicitudes_pendientes_gerente(
            contexto[
                "numero_empleado"
            ]
        )
    )

    resumen = {
        "total":
            len(
                solicitudes
            ),

        "vacaciones":
            sum(
                1
                for s in solicitudes
                if s[
                    "tipo_codigo"
                ] == "VACACIONES"
            ),

        "permisos":
            sum(
                1
                for s in solicitudes
                if s[
                    "tipo_codigo"
                ] == "PERMISO_TOTAL"
            ),

        "parciales":
            sum(
                1
                for s in solicitudes
                if s[
                    "tipo_codigo"
                ] == "PERMISO_PARCIAL"
            ),
    }

    return templates.TemplateResponse(
        "gerencia_permisos.html",
        {
            "request":
                request,

            **contexto,

            "solicitudes":
                solicitudes,

            "resumen":
                resumen,
        },
    )


@router.get(
    "/permisos/{id_process}"
)
def gerencia_permiso_detalle(
    request: Request,
    id_process: int,
):
    contexto, respuesta = (
        _validar_acceso_gerente(
            request
        )
    )

    if respuesta:
        return respuesta

    solicitud = (
        _solicitud_pendiente_detalle(
            id_process,
            contexto[
                "numero_empleado"
            ],
        )
    )

    if not solicitud:
        raise HTTPException(
            status_code=404,
            detail=(
                "La solicitud no existe, "
                "ya no está pendiente o no "
                "pertenece a tu gerencia."
            ),
        )

    return templates.TemplateResponse(
        "gerencia_permiso_detalle.html",
        {
            "request":
                request,

            **contexto,

            "solicitud":
                solicitud,
        },
    )


# ============================================================
# TRASPASOS
# SOLO LECTURA ✅
# ============================================================

def _historial_traspasos(
    numero_gerente: str,
):
    filas = portal_fetch_all(
        """
        SELECT TOP 200
            tp.ID_PROCESS,
            tp.ID_ESTATUS,

            tp.idEmpleadoTraspaso,
            tp.idEmpleadoSolicita,

            tp.idAreaOrigenFk,
            tp.idAreaDestinoFk,

            tp.fechaSolicitud,
            tp.fechaHoraConfirmacion,

            tp.descripcion,
            tp.idEmpleadoConfirma,

            tp.motivoRechazo,
            tp.idIntellisisFk,

            wsb.NAME_STATUS

        FROM dbo.traspasoPersonal tp

        LEFT JOIN dbo.w_status_bl wsb
            ON wsb.ID_STATUS
             = tp.ID_ESTATUS

            AND wsb.PROCESS_STATUS = 54

        WHERE
            CAST(
                tp.idEmpleadoSolicita
                AS varchar(50)
            ) = :numero_gerente

        ORDER BY
            tp.ID_PROCESS DESC
        """,
        {
            "numero_gerente":
                numero_gerente,
        },
    )

    numeros = [
        fila.get(
            "idEmpleadoTraspaso"
        )
        for fila in filas
    ]

    empleados = (
        _empleados_por_numeros(
            numeros
        )
    )

    resultado = []

    for fila in filas:

        numero = str(
            fila.get(
                "idEmpleadoTraspaso"
            )
            or ""
        ).strip()

        empleado = empleados.get(
            numero,
            {},
        )

        preparada = dict(
            fila
        )

        estado = int(
            fila.get(
                "ID_ESTATUS"
            )
            or 0
        )

        clase = {
            48: "pending",
            49: "approved",
            50: "rejected",
        }.get(
            estado,
            "neutral",
        )

        fecha_registro = (
            fila.get(
                "fechaHoraConfirmacion"
            )
            or fila.get(
                "fechaSolicitud"
            )
        )

        preparada.update({
            "numero_empleado":
                numero,

            "nombre_empleado":
                empleado.get(
                    "nombre_completo"
                )
                or f"Empleado {numero}",

            "estado_clase":
                clase,

            "estado_nombre":
                fila.get(
                    "NAME_STATUS"
                )
                or {
                    48:
                        "Pendiente de autorizar",

                    49:
                        "Traspaso autorizado",

                    50:
                        "Traspaso Rechazado",
                }.get(
                    estado,
                    "Sin estatus",
                ),

            "registro_texto":
                _fecha_hora(
                    fecha_registro
                ),
        })

        resultado.append(
            preparada
        )

    return resultado


def _catalogo_destinos():
    """
    El catálogo se arma con el maestro actual.

    Área:
        deptop

    Departamento:
        departamento_intelisis

    Sin modificar ninguna tabla.
    """

    filas = fetch_all(
        """
        SELECT DISTINCT

            COALESCE(
                NULLIF(
                    LTRIM(RTRIM(deptop)),
                    ''
                ),

                NULLIF(
                    LTRIM(RTRIM(sector)),
                    ''
                ),

                NULLIF(
                    LTRIM(RTRIM(agr)),
                    ''
                ),

                LTRIM(
                    RTRIM(
                        departamento_intelisis
                    )
                )
            ) AS area,

            LTRIM(
                RTRIM(
                    departamento_intelisis
                )
            ) AS departamento

        FROM dbo.ni_empleados_maestro

        WHERE
            ISNULL(
                activo_intelisis,
                1
            ) = 1

            AND NULLIF(
                LTRIM(
                    RTRIM(
                        departamento_intelisis
                    )
                ),
                ''
            ) IS NOT NULL

        ORDER BY
            area,
            departamento
        """
    )

    catalogo = {}

    for fila in filas:

        area = str(
            fila.get(
                "area"
            )
            or ""
        ).strip()

        departamento = str(
            fila.get(
                "departamento"
            )
            or ""
        ).strip()

        if (
            not area
            or not departamento
        ):
            continue

        catalogo.setdefault(
            area,
            [],
        )

        if (
            departamento
            not in catalogo[area]
        ):
            catalogo[
                area
            ].append(
                departamento
            )

    return [
        {
            "area":
                area,

            "departamentos":
                departamentos,
        }

        for area, departamentos
        in sorted(
            catalogo.items()
        )
    ]


@router.get(
    "/traspasos"
)
def gerencia_traspasos(
    request: Request,
):
    contexto, respuesta = (
        _validar_acceso_gerente(
            request
        )
    )

    if respuesta:
        return respuesta

    traspasos = _historial_traspasos(
        contexto[
            "numero_empleado"
        ]
    )

    resumen = {
        "pendientes":
            sum(
                1
                for t in traspasos
                if int(
                    t.get(
                        "ID_ESTATUS"
                    )
                    or 0
                ) == 48
            ),

        "autorizados":
            sum(
                1
                for t in traspasos
                if int(
                    t.get(
                        "ID_ESTATUS"
                    )
                    or 0
                ) == 49
            ),

        "rechazados":
            sum(
                1
                for t in traspasos
                if int(
                    t.get(
                        "ID_ESTATUS"
                    )
                    or 0
                ) == 50
            ),
    }

    return templates.TemplateResponse(
        "gerencia_traspasos.html",
        {
            "request":
                request,

            **contexto,

            "traspasos":
                traspasos,

            "resumen":
                resumen,
        },
    )


def _contexto_nuevo_traspaso(
    request,
    contexto,
    resultado=None,
    formulario=None,
):
    equipo = _equipo_gerente(
        contexto[
            "numero_empleado"
        ]
    )

    catalogo = (
        _catalogo_destinos()
    )

    return templates.TemplateResponse(
        "gerencia_traspaso_nuevo.html",
        {
            "request":
                request,

            **contexto,

            "equipo":
                equipo,

            "catalogo_destinos":
                catalogo,

            "resultado":
                resultado,

            "formulario":
                formulario
                or {},
        },
    )


@router.get(
    "/traspasos/nuevo"
)
def gerencia_traspaso_nuevo(
    request: Request,
):
    contexto, respuesta = (
        _validar_acceso_gerente(
            request
        )
    )

    if respuesta:
        return respuesta

    return _contexto_nuevo_traspaso(
        request,
        contexto,
    )


# ============================================================
# VALIDAR TRASPASO
#
# IMPORTANTE:
# NO INSERTA
# NO ACTUALIZA
# NO BORRA
# SOLO VALIDA Y MUESTRA RESULTADO
# ============================================================

@router.post(
    "/traspasos/nuevo/validar"
)
def gerencia_traspaso_validar(
    request: Request,

    numero_empleado: str = Form(...),

    area_destino: str = Form(...),

    departamento_destino: str = Form(...),

    motivo: str = Form(...),
):
    contexto, respuesta = (
        _validar_acceso_gerente(
            request
        )
    )

    if respuesta:
        return respuesta

    numero_empleado = str(
        numero_empleado
        or ""
    ).strip()

    area_destino = str(
        area_destino
        or ""
    ).strip()

    departamento_destino = str(
        departamento_destino
        or ""
    ).strip()

    motivo = str(
        motivo
        or ""
    ).strip()

    formulario = {
        "numero_empleado":
            numero_empleado,

        "area_destino":
            area_destino,

        "departamento_destino":
            departamento_destino,

        "motivo":
            motivo,
    }

    equipo = _mapa_equipo(
        contexto[
            "numero_empleado"
        ]
    )

    empleado = equipo.get(
        numero_empleado
    )

    errores = []

    if not empleado:
        errores.append(
            "El empleado seleccionado "
            "no pertenece actualmente "
            "a tu gerencia."
        )

    catalogo = (
        _catalogo_destinos()
    )

    destinos_validos = {
        item["area"]:
            set(
                item[
                    "departamentos"
                ]
            )

        for item in catalogo
    }

    if (
        area_destino
        not in destinos_validos
    ):
        errores.append(
            "El área de destino "
            "no es válida."
        )

    elif (
        departamento_destino
        not in destinos_validos[
            area_destino
        ]
    ):
        errores.append(
            "El departamento no "
            "corresponde al área "
            "seleccionada."
        )

    if not motivo:
        errores.append(
            "Captura el motivo "
            "del traspaso."
        )

    if empleado:

        origen = (
            empleado.get(
                "departamento_intelisis"
            )
            or "—"
        )

        if (
            origen.strip().upper()
            ==
            departamento_destino
            .strip()
            .upper()
        ):
            errores.append(
                "El empleado ya pertenece "
                "al departamento de destino."
            )

    else:
        origen = "—"

    resultado = {
        "ok":
            len(
                errores
            ) == 0,

        "errores":
            errores,

        "empleado":
            (
                empleado.get(
                    "nombre_completo"
                )
                if empleado
                else numero_empleado
            ),

        "numero_empleado":
            numero_empleado,

        "origen":
            origen,

        "area_destino":
            area_destino,

        "departamento_destino":
            departamento_destino,

        "motivo":
            motivo,
    }

    return _contexto_nuevo_traspaso(
        request,
        contexto,
        resultado=resultado,
        formulario=formulario,
    )