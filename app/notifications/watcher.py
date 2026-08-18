from __future__ import annotations

import logging
import threading
import time

from datetime import (
    date,
    datetime,
)

from app.database import (
    fetch_one,
    engine,
)

from sqlalchemy import text

from app.portalwyny_database import (
    portal_fetch_all,
    portal_fetch_one,
)

from app.notifications.repository import (
    get_notification_meta,
    notification_event_exists,
    remember_notification_event,
    set_notification_meta,
)

from app.notifications.service import (
    send_to_employee,
)


logger = logging.getLogger(
    "nova.notifications"
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

CHECK_SECONDS = 30

# ============================================================
# NOTIFICACIONES DE CHECADAS
# ============================================================

CHECADAS_BASELINE_PREFIX = (
    "checadas_baseline_v1"
)

# Una checada muy vieja ya no debe generar
# un "Bienvenido" horas después solamente
# porque el usuario activó notificaciones tarde.
CHECADA_MAX_AGE_MINUTES = 15

SOLICITUD_BASELINE_KEY = (
    "solicitudes_gerencia_baseline_v1"
)

SOLICITUD_RESPUESTA_BASELINE_KEY = (
    "solicitudes_empleado_respuestas_baseline_v1"
)


VIGILANCIA_PERMISOS_BASELINE_KEY = (
    "vigilancia_permisos_baseline_v1"
)


# Evita arrancar dos hilos dentro
# del mismo proceso.
_start_lock = threading.Lock()
_started = False


# ============================================================
# UTILIDADES
# ============================================================

def _texto(
    valor,
) -> str:

    if valor is None:
        return ""

    return str(
        valor
    ).strip()


def _fecha_texto(
    valor,
) -> str:

    if not valor:
        return "-"

    if isinstance(
        valor,
        datetime,
    ):
        return valor.strftime(
            "%d/%m/%Y"
        )

    if isinstance(
        valor,
        date,
    ):
        return valor.strftime(
            "%d/%m/%Y"
        )

    texto = str(
        valor
    ).strip()

    try:

        fecha = datetime.fromisoformat(
            texto[:10]
        )

        return fecha.strftime(
            "%d/%m/%Y"
        )

    except Exception:
        return texto[:10]


def _event_key(
    solicitud_id,
) -> str:

    return (
        "solicitud-gerencia:"
        + str(
            solicitud_id
        )
    )


# ============================================================
# SOLICITUDES PENDIENTES
#
# SOLO LECTURA EN portalWyny
# ============================================================

def _obtener_solicitudes_pendientes():

    return portal_fetch_all(
        """
        SELECT

            es.ID_PROCESS,
            es.ID_ESTATUS,

            LTRIM(
                RTRIM(
                    es.idEmpleado
                )
            ) AS idEmpleado,

            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,

            es.horaInicio,
            es.horaFinal,

            es.diasTotales,
            es.diasHabiles,

            CAST(
                es.motivoPermiso
                AS varchar(max)
            ) AS motivoPermiso,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM
            dbo.empleadosSolicitudes es

        LEFT JOIN
            dbo.usuarioEmpleado ue
                ON ue.idUsuarioFk
                    = es.idUsuarioFk

        LEFT JOIN
            dbo.tiposPermisos tp
                ON tp.ID_PROCESS
                    = es.idTipoPermisoFk

        WHERE
            es.ID_ESTATUS = 21

            AND es.fechaInicio >=
                DATEFROMPARTS(
                    YEAR(GETDATE()),
                    1,
                    1
                )

            AND es.fechaInicio <
                DATEFROMPARTS(
                    YEAR(GETDATE()) + 1,
                    1,
                    1
                )

        ORDER BY
            es.ID_PROCESS
        """
    )


def _obtener_solicitud(
    solicitud_id: int,
):

    return portal_fetch_one(
        """
        SELECT TOP 1

            es.ID_PROCESS,
            es.ID_ESTATUS,

            LTRIM(
                RTRIM(
                    es.idEmpleado
                )
            ) AS idEmpleado,

            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,

            es.horaInicio,
            es.horaFinal,

            es.diasTotales,
            es.diasHabiles,

            CAST(
                es.motivoPermiso
                AS varchar(max)
            ) AS motivoPermiso,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM
            dbo.empleadosSolicitudes es

        LEFT JOIN
            dbo.usuarioEmpleado ue
                ON ue.idUsuarioFk
                    = es.idUsuarioFk

        LEFT JOIN
            dbo.tiposPermisos tp
                ON tp.ID_PROCESS
                    = es.idTipoPermisoFk

        WHERE
            es.ID_PROCESS = :id_process
        """,
        {
            "id_process":
                int(
                    solicitud_id
                ),
        },
    )


# ============================================================
# GERENTE DEL EMPLEADO
#
# SOLO LECTURA EN NominaInteligente
# ============================================================

def _obtener_gerente(
    numero_empleado: str,
):

    empleado = fetch_one(
        """
        SELECT TOP 1

            numero_empleado,
            nombre_completo,

            gerente,
            nombre_gerente,

            director,
            nombre_director,

            categoria

        FROM
            dbo.ni_empleados_maestro

        WHERE
            LTRIM(
                RTRIM(
                    numero_empleado
                )
            ) = :numero_empleado
        """,
        {
            "numero_empleado":
                str(
                    numero_empleado
                ).strip(),
        },
    )

    if not empleado:
        return None


    numero = _texto(
        empleado.get(
            "numero_empleado"
        )
    )

    gerente = _texto(
        empleado.get(
            "gerente"
        )
    )


    # No mandamos una solicitud
    # al mismo empleado.
    #
    # Algunos gerentes pueden tener
    # su propio número en "gerente".
    #
    # Ese caso de autorización superior
    # lo resolveremos aparte cuando
    # definamos ese flujo.

    if (
        not gerente
        or gerente == numero
    ):
        return None


    return {
        "numero_empleado":
            gerente,

        "nombre":
            _texto(
                empleado.get(
                    "nombre_gerente"
                )
            ),
    }

# ============================================================
# TEXTO DE NOTIFICACIÓN
# ============================================================

def _datos_notificacion(
    solicitud: dict,
):

    tipo = int(
        solicitud.get(
            "idTipoPermisoFk"
        )
        or 0
    )


    if tipo == 1:

        titulo = (
            "🏖️ Vacaciones por autorizar"
        )

    elif tipo in (
        2,
        3,
    ):

        titulo = (
            "📅 Permiso por autorizar"
        )

    else:

        titulo = (
            "🕒 Permiso parcial por autorizar"
        )


    empleado = (
        _texto(
            solicitud.get(
                "nombreCompleto"
            )
        )
        or (
            "Empleado "
            + _texto(
                solicitud.get(
                    "idEmpleado"
                )
            )
        )
    )


    fecha_inicio = _fecha_texto(
        solicitud.get(
            "fechaInicio"
        )
    )

    fecha_final = _fecha_texto(
        solicitud.get(
            "fechaFinal"
        )
    )


    if (
        fecha_final
        and fecha_final != "-"
        and fecha_final
            != fecha_inicio
    ):

        periodo = (
            f"{fecha_inicio}"
            f" → "
            f"{fecha_final}"
        )

    else:

        periodo = fecha_inicio


    body = (
        f"{empleado}\n"
        f"{periodo}"
    )


    solicitud_id = int(
        solicitud[
            "ID_PROCESS"
        ]
    )


    return {
        "title":
            titulo,

        "body":
            body,

        "url":
            (
                "/gerencia/permisos/"
                + str(
                    solicitud_id
                )
            ),

        "tag":
            (
                "nova-solicitud-"
                + str(
                    solicitud_id
                )
            ),
    }


# ============================================================
# PRIMER ARRANQUE
#
# No manda pendientes históricos.
# Solo crea la línea base local.
# ============================================================

def _crear_baseline(
    solicitudes: list,
):

    total = 0

    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        key = _event_key(
            solicitud_id
        )


        if notification_event_exists(
            key
        ):
            continue


        remember_notification_event(
            event_key=key,
            event_type=(
                "SOLICITUD_GERENCIA_BASELINE"
            ),
            recipient_employee=(
                "BASELINE"
            ),
            source_id=str(
                solicitud_id
            ),
            sent=False,
        )

        total += 1


    set_notification_meta(
        SOLICITUD_BASELINE_KEY,
        "1",
    )


    print(
        "[NOVA PUSH] "
        f"Baseline de solicitudes creado: "
        f"{total} solicitud(es)."
    )


    return total


# ============================================================
# REVISIÓN AUTOMÁTICA
# ============================================================

def check_permission_notifications():

    solicitudes = (
        _obtener_solicitudes_pendientes()
    )


    baseline = get_notification_meta(
        SOLICITUD_BASELINE_KEY
    )


    if baseline != "1":

        total = _crear_baseline(
            solicitudes
        )

        return {
            "ok": True,
            "baseline_created":
                True,
            "baseline_requests":
                total,
            "sent":
                0,
        }


    resultado = {
        "ok": True,
        "baseline_created":
            False,
        "checked":
            len(
                solicitudes
            ),
        "new":
            0,
        "sent":
            0,
        "without_manager":
            0,
        "without_device":
            0,
        "failed":
            0,
    }


    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        key = _event_key(
            solicitud_id
        )


        # Ya fue atendida por
        # nuestro sistema de avisos.
        if notification_event_exists(
            key
        ):
            continue


        resultado[
            "new"
        ] += 1


        numero_empleado = _texto(
            solicitud.get(
                "idEmpleado"
            )
        )


        gerente = _obtener_gerente(
            numero_empleado
        )


        if not gerente:

            resultado[
                "without_manager"
            ] += 1

            continue


        datos = _datos_notificacion(
            solicitud
        )


        envio = send_to_employee(
            gerente[
                "numero_empleado"
            ],

            title=datos[
                "title"
            ],

            body=datos[
                "body"
            ],

            url=datos[
                "url"
            ],

            tag=datos[
                "tag"
            ],
        )


        if envio[
            "sent"
        ] > 0:

            remember_notification_event(
                event_key=key,
                event_type=(
                    "SOLICITUD_GERENCIA"
                ),
                recipient_employee=(
                    gerente[
                        "numero_empleado"
                    ]
                ),
                source_id=str(
                    solicitud_id
                ),
                sent=True,
            )


            resultado[
                "sent"
            ] += 1


            print(
                "[NOVA PUSH] "
                f"Solicitud #{solicitud_id} "
                f"notificada a gerente "
                f"{gerente['numero_empleado']}."
            )


        elif envio[
            "total"
        ] == 0:

            # NO registramos el evento.
            #
            # Así, si el gerente activa
            # sus notificaciones después,
            # el watcher vuelve a intentarlo.
            resultado[
                "without_device"
            ] += 1


        else:

            resultado[
                "failed"
            ] += 1


    return resultado


# ============================================================
# PRUEBA MANUAL
#
# NO MARCA LA SOLICITUD COMO NOTIFICADA.
# Sirve para probar con una solicitud existente.
# ============================================================

def test_permission_notification(
    solicitud_id: int,
):

    solicitud = _obtener_solicitud(
        int(
            solicitud_id
        )
    )


    if not solicitud:

        return {
            "ok": False,
            "error":
                "Solicitud no encontrada.",
        }


    numero_empleado = _texto(
        solicitud.get(
            "idEmpleado"
        )
    )


    gerente = _obtener_gerente(
        numero_empleado
    )


    if not gerente:

        return {
            "ok": False,
            "error": (
                "No fue posible resolver "
                "un gerente distinto al "
                "propio empleado."
            ),
            "empleado":
                numero_empleado,
        }


    datos = _datos_notificacion(
        solicitud
    )


    envio = send_to_employee(
        gerente[
            "numero_empleado"
        ],

        title=(
            "🧪 PRUEBA · "
            + datos[
                "title"
            ]
        ),

        body=datos[
            "body"
        ],

        url=datos[
            "url"
        ],

        tag=(
            "nova-prueba-solicitud-"
            + str(
                solicitud_id
            )
        ),
    )


    return {
        "ok":
            envio[
                "sent"
            ] > 0,

        "solicitud":
            int(
                solicitud_id
            ),

        "empleado":
            numero_empleado,

        "gerente":
            gerente,

        "envio":
            envio,
    }


# ============================================================
# CHECADAS
#
# SOLO LECTURA EN NominaInteligente
# ============================================================

def _obtener_checadas_validas_hoy():

    with engine.connect() as conn:

        rows = conn.execute(
            text(
                """
                SELECT
                    LTRIM(
                        RTRIM(
                            j.numero_empleado
                        )
                    ) AS numero_empleado,

                    j.nombre_completo,
                    j.fecha_operativa,

                    j.entrada_esperada,
                    j.salida_esperada,

                    j.checada_entrada_valida,
                    j.checada_salida_valida

                FROM
                    dbo.ni_jornada_diaria j

                WHERE
                    j.fecha_operativa
                        = CAST(GETDATE() AS date)

                    AND (
                        j.checada_entrada_valida
                            IS NOT NULL

                        OR

                        j.checada_salida_valida
                            IS NOT NULL
                    )
                """
            )
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def _checadas_fecha_hoy():

    with engine.connect() as conn:

        row = conn.execute(
            text(
                """
                SELECT
                    CAST(GETDATE() AS date)
                    AS fecha
                """
            )
        ).mappings().first()

    if not row:
        return date.today()

    valor = row["fecha"]

    if isinstance(
        valor,
        datetime,
    ):
        return valor.date()

    return valor


def _checada_event_key(
    numero_empleado: str,
    fecha_operativa,
    tipo: str,
):

    return (
        "checada:"
        + str(fecha_operativa)
        + ":"
        + str(numero_empleado).strip()
        + ":"
        + str(tipo).upper()
    )


def _checada_baseline_key(
    fecha_operativa,
):

    return (
        CHECADAS_BASELINE_PREFIX
        + ":"
        + str(fecha_operativa)
    )


def _hora_checada(
    valor,
) -> str:

    if not valor:
        return "--:--"

    if isinstance(
        valor,
        datetime,
    ):
        return valor.strftime(
            "%H:%M"
        )

    try:

        fecha = datetime.fromisoformat(
            str(valor)
        )

        return fecha.strftime(
            "%H:%M"
        )

    except Exception:

        texto = str(valor)

        if len(texto) >= 16:
            return texto[11:16]

        return texto


def _es_checada_reciente(
    valor,
) -> bool:

    if not valor:
        return False

    if isinstance(
        valor,
        datetime,
    ):
        fecha = valor

    else:

        try:

            fecha = datetime.fromisoformat(
                str(valor)
            )

        except Exception:
            return False


    ahora = datetime.now()

    diferencia = (
        ahora - fecha
    ).total_seconds() / 60.0


    return (
        -2
        <= diferencia
        <= CHECADA_MAX_AGE_MINUTES
    )


def _crear_baseline_checadas(
    jornadas: list,
    fecha_operativa,
):

    total = 0


    for jornada in jornadas:

        numero_empleado = _texto(
            jornada.get(
                "numero_empleado"
            )
        )


        if not numero_empleado:
            continue


        entrada = jornada.get(
            "checada_entrada_valida"
        )

        salida = jornada.get(
            "checada_salida_valida"
        )


        if entrada:

            key = _checada_event_key(
                numero_empleado,
                fecha_operativa,
                "ENTRADA",
            )

            if not notification_event_exists(
                key
            ):

                remember_notification_event(
                    event_key=key,
                    event_type=(
                        "CHECADA_ENTRADA_BASELINE"
                    ),
                    recipient_employee=(
                        numero_empleado
                    ),
                    source_id=str(
                        entrada
                    ),
                    sent=False,
                )

                total += 1


        if salida:

            key = _checada_event_key(
                numero_empleado,
                fecha_operativa,
                "SALIDA",
            )

            if not notification_event_exists(
                key
            ):

                remember_notification_event(
                    event_key=key,
                    event_type=(
                        "CHECADA_SALIDA_BASELINE"
                    ),
                    recipient_employee=(
                        numero_empleado
                    ),
                    source_id=str(
                        salida
                    ),
                    sent=False,
                )

                total += 1


    set_notification_meta(
        _checada_baseline_key(
            fecha_operativa
        ),
        "1",
    )


    print(
        "[NOVA PUSH] "
        "Baseline de checadas creado: "
        f"{total} evento(s)."
    )


    return total


def _notificar_entrada(
    jornada: dict,
):

    numero_empleado = _texto(
        jornada.get(
            "numero_empleado"
        )
    )

    nombre = (
        _texto(
            jornada.get(
                "nombre_completo"
            )
        )
        or numero_empleado
    )

    entrada = jornada.get(
        "checada_entrada_valida"
    )

    hora = _hora_checada(
        entrada
    )


    return send_to_employee(
        numero_empleado,

        title=(
            "👋 NOVA · Entrada registrada"
        ),

        body=(
            f"¡Bienvenido(a), {nombre}!\n"
            f"Tu checada de entrada "
            f"fue registrada a las {hora}."
        ),

        url=(
            "/asistencia/mis-checadas"
        ),

        tag=(
            "nova-entrada-"
            + numero_empleado
            + "-"
            + str(
                jornada.get(
                    "fecha_operativa"
                )
            )
        ),
    )


def _notificar_salida(
    jornada: dict,
):

    numero_empleado = _texto(
        jornada.get(
            "numero_empleado"
        )
    )

    nombre = (
        _texto(
            jornada.get(
                "nombre_completo"
            )
        )
        or numero_empleado
    )

    salida = jornada.get(
        "checada_salida_valida"
    )

    hora = _hora_checada(
        salida
    )


    return send_to_employee(
        numero_empleado,

        title=(
            "👋 NOVA · Salida registrada"
        ),

        body=(
            f"Hasta luego, {nombre}.\n"
            f"Tu checada de salida "
            f"fue registrada a las {hora}."
        ),

        url=(
            "/asistencia/mis-checadas"
        ),

        tag=(
            "nova-salida-"
            + numero_empleado
            + "-"
            + str(
                jornada.get(
                    "fecha_operativa"
                )
            )
        ),
    )


def check_attendance_notifications():

    fecha_operativa = (
        _checadas_fecha_hoy()
    )

    jornadas = (
        _obtener_checadas_validas_hoy()
    )


    baseline_key = (
        _checada_baseline_key(
            fecha_operativa
        )
    )


    if (
        get_notification_meta(
            baseline_key
        )
        != "1"
    ):

        total = (
            _crear_baseline_checadas(
                jornadas,
                fecha_operativa,
            )
        )

        return {
            "ok": True,
            "baseline_created": True,
            "baseline_events": total,
            "sent": 0,
        }


    resultado = {
        "ok": True,
        "baseline_created": False,
        "checked": len(
            jornadas
        ),
        "entries_sent": 0,
        "exits_sent": 0,
        "without_device": 0,
        "old_skipped": 0,
        "failed": 0,
    }


    for jornada in jornadas:

        numero_empleado = _texto(
            jornada.get(
                "numero_empleado"
            )
        )


        if not numero_empleado:
            continue


        # ====================================================
        # ENTRADA
        # ====================================================

        entrada = jornada.get(
            "checada_entrada_valida"
        )


        if entrada:

            key = _checada_event_key(
                numero_empleado,
                fecha_operativa,
                "ENTRADA",
            )


            if not notification_event_exists(
                key
            ):

                # Si ya pasó mucho tiempo,
                # no mandamos un "Bienvenido"
                # tardío.
                if not _es_checada_reciente(
                    entrada
                ):

                    remember_notification_event(
                        event_key=key,
                        event_type=(
                            "CHECADA_ENTRADA_OMITIDA"
                        ),
                        recipient_employee=(
                            numero_empleado
                        ),
                        source_id=str(
                            entrada
                        ),
                        sent=False,
                    )

                    resultado[
                        "old_skipped"
                    ] += 1

                else:

                    envio = (
                        _notificar_entrada(
                            jornada
                        )
                    )


                    if envio["sent"] > 0:

                        remember_notification_event(
                            event_key=key,
                            event_type=(
                                "CHECADA_ENTRADA"
                            ),
                            recipient_employee=(
                                numero_empleado
                            ),
                            source_id=str(
                                entrada
                            ),
                            sent=True,
                        )

                        resultado[
                            "entries_sent"
                        ] += 1


                        print(
                            "[NOVA PUSH] "
                            f"Entrada de "
                            f"{numero_empleado} "
                            f"notificada "
                            f"a las "
                            f"{_hora_checada(entrada)}."
                        )


                    elif envio["total"] == 0:

                        # No lo marcamos todavía.
                        #
                        # Si activa notificaciones
                        # dentro de los próximos
                        # minutos, todavía podrá
                        # recibirlo.
                        resultado[
                            "without_device"
                        ] += 1


                    else:

                        resultado[
                            "failed"
                        ] += 1


        # ====================================================
        # SALIDA
        # ====================================================

        salida = jornada.get(
            "checada_salida_valida"
        )


        if salida:

            key = _checada_event_key(
                numero_empleado,
                fecha_operativa,
                "SALIDA",
            )


            if not notification_event_exists(
                key
            ):

                if not _es_checada_reciente(
                    salida
                ):

                    remember_notification_event(
                        event_key=key,
                        event_type=(
                            "CHECADA_SALIDA_OMITIDA"
                        ),
                        recipient_employee=(
                            numero_empleado
                        ),
                        source_id=str(
                            salida
                        ),
                        sent=False,
                    )

                    resultado[
                        "old_skipped"
                    ] += 1

                else:

                    envio = (
                        _notificar_salida(
                            jornada
                        )
                    )


                    if envio["sent"] > 0:

                        remember_notification_event(
                            event_key=key,
                            event_type=(
                                "CHECADA_SALIDA"
                            ),
                            recipient_employee=(
                                numero_empleado
                            ),
                            source_id=str(
                                salida
                            ),
                            sent=True,
                        )

                        resultado[
                            "exits_sent"
                        ] += 1


                        print(
                            "[NOVA PUSH] "
                            f"Salida de "
                            f"{numero_empleado} "
                            f"notificada "
                            f"a las "
                            f"{_hora_checada(salida)}."
                        )


                    elif envio["total"] == 0:

                        resultado[
                            "without_device"
                        ] += 1


                    else:

                        resultado[
                            "failed"
                        ] += 1


    return resultado

def test_attendance_notification(
    numero_empleado: str,
    tipo: str = "ENTRADA",
):

    numero_empleado = str(
        numero_empleado
    ).strip()

    tipo = str(
        tipo
    ).strip().upper()


    if tipo not in (
        "ENTRADA",
        "SALIDA",
    ):

        return {
            "ok": False,
            "error": (
                "tipo debe ser "
                "ENTRADA o SALIDA"
            ),
        }


    with engine.connect() as conn:

        row = conn.execute(
            text(
                """
                SELECT TOP 1

                    LTRIM(
                        RTRIM(
                            numero_empleado
                        )
                    ) AS numero_empleado,

                    nombre_completo,
                    fecha_operativa,

                    checada_entrada_valida,
                    checada_salida_valida

                FROM
                    dbo.ni_jornada_diaria

                WHERE
                    LTRIM(
                        RTRIM(
                            numero_empleado
                        )
                    ) = :numero_empleado

                    AND (
                        checada_entrada_valida
                            IS NOT NULL

                        OR

                        checada_salida_valida
                            IS NOT NULL
                    )

                ORDER BY
                    fecha_operativa DESC
                """
            ),
            {
                "numero_empleado":
                    numero_empleado,
            },
        ).mappings().first()


    if not row:

        return {
            "ok": False,
            "error": (
                "No se encontró "
                "ninguna jornada con checada."
            ),
        }


    jornada = dict(
        row
    )


    if tipo == "ENTRADA":

        if not jornada.get(
            "checada_entrada_valida"
        ):

            return {
                "ok": False,
                "error": (
                    "La jornada no tiene "
                    "entrada válida."
                ),
            }


        nombre = (
            _texto(
                jornada.get(
                    "nombre_completo"
                )
            )
            or numero_empleado
        )

        hora = _hora_checada(
            jornada[
                "checada_entrada_valida"
            ]
        )


        envio = send_to_employee(
            numero_empleado,

            title=(
                "🧪 PRUEBA · "
                "👋 Entrada registrada"
            ),

            body=(
                f"¡Bienvenido(a), {nombre}!\n"
                f"Tu checada de entrada "
                f"fue registrada a las {hora}."
            ),

            url=(
                "/asistencia/mis-checadas"
            ),

            tag=(
                "nova-prueba-entrada-"
                + numero_empleado
            ),
        )


    else:

        if not jornada.get(
            "checada_salida_valida"
        ):

            return {
                "ok": False,
                "error": (
                    "La jornada no tiene "
                    "salida válida."
                ),
            }


        nombre = (
            _texto(
                jornada.get(
                    "nombre_completo"
                )
            )
            or numero_empleado
        )

        hora = _hora_checada(
            jornada[
                "checada_salida_valida"
            ]
        )


        envio = send_to_employee(
            numero_empleado,

            title=(
                "🧪 PRUEBA · "
                "👋 Salida registrada"
            ),

            body=(
                f"Hasta luego, {nombre}.\n"
                f"Tu checada de salida "
                f"fue registrada a las {hora}."
            ),

            url=(
                "/asistencia/mis-checadas"
            ),

            tag=(
                "nova-prueba-salida-"
                + numero_empleado
            ),
        )


    return {
        "ok":
            envio["sent"] > 0,

        "numero_empleado":
            numero_empleado,

        "tipo":
            tipo,

        "jornada":
            jornada,

        "envio":
            envio,
    }

# ============================================================
# RESPUESTA DE SOLICITUD → EMPLEADO
#
# 23 = AUTORIZADA
# 24 = RECHAZADA
#
# SOLO LECTURA EN portalWyny
# ============================================================

def _respuesta_event_key(
    solicitud_id: int,
    id_estatus: int,
) -> str:

    if int(id_estatus) == 23:
        estado = "AUTORIZADA"
    else:
        estado = "RECHAZADA"

    return (
        "solicitud-empleado:"
        + str(solicitud_id)
        + ":"
        + estado
    )


def _obtener_solicitudes_resueltas():

    return portal_fetch_all(
        """
        SELECT

            es.ID_PROCESS,
            es.ID_ESTATUS,

            LTRIM(
                RTRIM(
                    es.idEmpleado
                )
            ) AS idEmpleado,

            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,
            es.fechaConfirmacion,

            es.horaInicio,
            es.horaFinal,

            es.diasTotales,
            es.diasHabiles,

            CAST(
                es.motivoPermiso
                AS varchar(max)
            ) AS motivoPermiso,

            CAST(
                es.motivoRechazo
                AS varchar(max)
            ) AS motivoRechazo,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM
            dbo.empleadosSolicitudes es

        LEFT JOIN
            dbo.usuarioEmpleado ue
                ON ue.idUsuarioFk
                    = es.idUsuarioFk

        LEFT JOIN
            dbo.tiposPermisos tp
                ON tp.ID_PROCESS
                    = es.idTipoPermisoFk

        WHERE
            es.ID_ESTATUS IN (
                23,
                24
            )

            AND es.fechaSolicitud >=
                DATEFROMPARTS(
                    YEAR(GETDATE()),
                    1,
                    1
                )

        ORDER BY
            es.ID_PROCESS
        """
    )


def _obtener_solicitud_resuelta(
    solicitud_id: int,
):

    return portal_fetch_one(
        """
        SELECT TOP 1

            es.ID_PROCESS,
            es.ID_ESTATUS,

            LTRIM(
                RTRIM(
                    es.idEmpleado
                )
            ) AS idEmpleado,

            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,
            es.fechaConfirmacion,

            es.horaInicio,
            es.horaFinal,

            es.diasTotales,
            es.diasHabiles,

            CAST(
                es.motivoPermiso
                AS varchar(max)
            ) AS motivoPermiso,

            CAST(
                es.motivoRechazo
                AS varchar(max)
            ) AS motivoRechazo,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM
            dbo.empleadosSolicitudes es

        LEFT JOIN
            dbo.usuarioEmpleado ue
                ON ue.idUsuarioFk
                    = es.idUsuarioFk

        LEFT JOIN
            dbo.tiposPermisos tp
                ON tp.ID_PROCESS
                    = es.idTipoPermisoFk

        WHERE
            es.ID_PROCESS = :id_process

            AND es.ID_ESTATUS IN (
                23,
                24
            )
        """,
        {
            "id_process":
                int(
                    solicitud_id
                ),
        },
    )


def _datos_respuesta_solicitud(
    solicitud: dict,
):

    id_estatus = int(
        solicitud.get(
            "ID_ESTATUS"
        )
        or 0
    )

    tipo = int(
        solicitud.get(
            "idTipoPermisoFk"
        )
        or 0
    )


    # --------------------------------------------------------
    # TIPO DE SOLICITUD
    # --------------------------------------------------------

    if tipo == 1:

        nombre_tipo = (
            "vacaciones"
        )

        icono = "🏖️"

    elif tipo in (
        2,
        3,
    ):

        nombre_tipo = (
            "permiso"
        )

        icono = "📅"

    else:

        nombre_tipo = (
            "permiso parcial"
        )

        icono = "🕒"


    # --------------------------------------------------------
    # FECHAS
    # --------------------------------------------------------

    fecha_inicio = _fecha_texto(
        solicitud.get(
            "fechaInicio"
        )
    )

    fecha_final = _fecha_texto(
        solicitud.get(
            "fechaFinal"
        )
    )


    if (
        fecha_final
        and fecha_final != "-"
        and fecha_final != fecha_inicio
    ):

        periodo = (
            f"{fecha_inicio}"
            f" → "
            f"{fecha_final}"
        )

    else:

        periodo = fecha_inicio


    # --------------------------------------------------------
    # AUTORIZADA
    # --------------------------------------------------------

    if id_estatus == 23:

        title = (
            f"✅ {icono} Solicitud autorizada"
        )

        body = (
            f"Tu solicitud de "
            f"{nombre_tipo} fue autorizada.\n"
            f"{periodo}"
        )

        url = (
            "/solicitudes"
            "?estado=AUTORIZADOS"
        )

        event_type = (
            "SOLICITUD_AUTORIZADA"
        )

        estado_tag = (
            "autorizada"
        )


    # --------------------------------------------------------
    # RECHAZADA
    # --------------------------------------------------------

    else:

        title = (
            f"❌ {icono} Solicitud rechazada"
        )

        body = (
            f"Tu solicitud de "
            f"{nombre_tipo} fue rechazada.\n"
            f"{periodo}"
        )


        motivo = _texto(
            solicitud.get(
                "motivoRechazo"
            )
        )


        if motivo:

            body += (
                "\nMotivo: "
                + motivo
            )


        url = (
            "/solicitudes"
            "?estado=RECHAZADOS"
        )

        event_type = (
            "SOLICITUD_RECHAZADA"
        )

        estado_tag = (
            "rechazada"
        )


    solicitud_id = int(
        solicitud[
            "ID_PROCESS"
        ]
    )


    return {
        "title":
            title,

        "body":
            body,

        "url":
            url,

        "tag":
            (
                "nova-solicitud-"
                + estado_tag
                + "-"
                + str(
                    solicitud_id
                )
            ),

        "event_type":
            event_type,
    }


# ============================================================
# BASELINE
#
# Evita avisar todas las autorizaciones/rechazos
# que ya existían antes de activar esta función.
# ============================================================

def _crear_baseline_respuestas(
    solicitudes: list,
):

    total = 0


    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        id_estatus = int(
            solicitud[
                "ID_ESTATUS"
            ]
        )


        key = _respuesta_event_key(
            solicitud_id,
            id_estatus,
        )


        if notification_event_exists(
            key
        ):
            continue


        remember_notification_event(
            event_key=key,
            event_type=(
                "SOLICITUD_RESPUESTA_BASELINE"
            ),
            recipient_employee=(
                _texto(
                    solicitud.get(
                        "idEmpleado"
                    )
                )
                or "BASELINE"
            ),
            source_id=str(
                solicitud_id
            ),
            sent=False,
        )


        total += 1


    set_notification_meta(
        SOLICITUD_RESPUESTA_BASELINE_KEY,
        "1",
    )


    print(
        "[NOVA PUSH] "
        "Baseline de respuestas creado: "
        f"{total} solicitud(es)."
    )


    return total


# ============================================================
# REVISIÓN AUTOMÁTICA
# ============================================================

def check_employee_request_notifications():

    solicitudes = (
        _obtener_solicitudes_resueltas()
    )


    baseline = get_notification_meta(
        SOLICITUD_RESPUESTA_BASELINE_KEY
    )


    if baseline != "1":

        total = (
            _crear_baseline_respuestas(
                solicitudes
            )
        )

        return {
            "ok": True,
            "baseline_created":
                True,
            "baseline_requests":
                total,
            "sent":
                0,
        }


    resultado = {
        "ok": True,
        "baseline_created":
            False,
        "checked":
            len(
                solicitudes
            ),
        "new":
            0,
        "sent":
            0,
        "without_device":
            0,
        "failed":
            0,
    }


    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        id_estatus = int(
            solicitud[
                "ID_ESTATUS"
            ]
        )


        key = _respuesta_event_key(
            solicitud_id,
            id_estatus,
        )


        if notification_event_exists(
            key
        ):
            continue


        resultado[
            "new"
        ] += 1


        numero_empleado = _texto(
            solicitud.get(
                "idEmpleado"
            )
        )


        if not numero_empleado:
            continue


        datos = (
            _datos_respuesta_solicitud(
                solicitud
            )
        )


        envio = send_to_employee(
            numero_empleado,

            title=datos[
                "title"
            ],

            body=datos[
                "body"
            ],

            url=datos[
                "url"
            ],

            tag=datos[
                "tag"
            ],
        )


        if envio[
            "sent"
        ] > 0:

            remember_notification_event(
                event_key=key,
                event_type=(
                    datos[
                        "event_type"
                    ]
                ),
                recipient_employee=(
                    numero_empleado
                ),
                source_id=str(
                    solicitud_id
                ),
                sent=True,
            )


            resultado[
                "sent"
            ] += 1


            print(
                "[NOVA PUSH] "
                f"Respuesta solicitud "
                f"#{solicitud_id} "
                f"notificada al empleado "
                f"{numero_empleado}."
            )


        elif envio[
            "total"
        ] == 0:

            # No marcamos el evento todavía.
            #
            # Si después activa sus
            # notificaciones, NOVA podrá
            # volver a intentarlo.
            resultado[
                "without_device"
            ] += 1


        else:

            resultado[
                "failed"
            ] += 1


    return resultado


# ============================================================
# PRUEBA MANUAL
#
# NO registra el evento como enviado.
# ============================================================

def test_employee_request_notification(
    solicitud_id: int,
):

    solicitud = (
        _obtener_solicitud_resuelta(
            int(
                solicitud_id
            )
        )
    )


    if not solicitud:

        return {
            "ok": False,
            "error": (
                "La solicitud no existe "
                "o todavía está pendiente."
            ),
        }


    numero_empleado = _texto(
        solicitud.get(
            "idEmpleado"
        )
    )


    if not numero_empleado:

        return {
            "ok": False,
            "error": (
                "La solicitud no tiene "
                "empleado asociado."
            ),
        }


    datos = (
        _datos_respuesta_solicitud(
            solicitud
        )
    )


    envio = send_to_employee(
        numero_empleado,

        title=(
            "🧪 PRUEBA · "
            + datos[
                "title"
            ]
        ),

        body=datos[
            "body"
        ],

        url=datos[
            "url"
        ],

        tag=(
            "nova-prueba-respuesta-"
            + str(
                solicitud_id
            )
        ),
    )


    return {
        "ok":
            envio[
                "sent"
            ] > 0,

        "solicitud":
            int(
                solicitud_id
            ),

        "empleado":
            numero_empleado,

        "estatus":
            int(
                solicitud[
                    "ID_ESTATUS"
                ]
            ),

        "envio":
            envio,
    }


# ============================================================
# VIGILANCIA · PERMISOS AUTORIZADOS
#
# SOLO LECTURA en portalWyny y NominaInteligente.
#
# El control de duplicados se guarda únicamente en la
# base local del sistema Web Push de NOVA.
# ============================================================

def _vigilancia_event_key(
    solicitud_id: int,
) -> str:

    return (
        "vigilancia-permiso-autorizado:"
        + str(
            int(
                solicitud_id
            )
        )
    )


def _fecha_iso(
    valor,
) -> str:

    if not valor:
        return date.today().isoformat()

    if isinstance(
        valor,
        datetime,
    ):
        return valor.date().isoformat()

    if isinstance(
        valor,
        date,
    ):
        return valor.isoformat()

    texto = str(
        valor
    ).strip()

    if len(texto) >= 10:
        return texto[:10]

    return date.today().isoformat()


def _hora_permiso(
    valor,
) -> str:

    if not valor:
        return ""

    if hasattr(
        valor,
        "strftime",
    ):

        try:
            return valor.strftime(
                "%H:%M"
            )

        except Exception:
            pass

    texto = str(
        valor
    ).strip()

    if len(texto) >= 5:
        return texto[:5]

    return texto


def _obtener_destinatarios_vigilancia():

    """
    Obtiene usuarios activos que tienen asignado
    el rol VIGILANCIA.

    SOLO LECTURA en NominaInteligente.
    """

    with engine.connect() as conn:

        rows = conn.execute(
            text(
                """
                SELECT DISTINCT

                    LTRIM(
                        RTRIM(
                            u.numero_empleado
                        )
                    ) AS numero_empleado,

                    u.nombre_usuario AS nombre_completo

                FROM dbo.ni_usuarios u

                INNER JOIN dbo.ni_usuario_roles ur
                    ON ur.usuario_id = u.id
                    AND ur.activo = 1

                INNER JOIN dbo.ni_roles r
                    ON r.id = ur.rol_id
                    AND r.activo = 1

                WHERE
                    u.activo = 1

                    AND u.numero_empleado
                        IS NOT NULL

                    AND LTRIM(
                        RTRIM(
                            u.numero_empleado
                        )
                    ) <> ''

                    AND UPPER(
                        LTRIM(
                            RTRIM(
                                r.codigo
                            )
                        )
                    ) = 'VIGILANCIA'

                ORDER BY
                    numero_empleado
                """
            )
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def _obtener_permisos_autorizados_vigilancia():

    """
    Lee únicamente autorizaciones que todavía pueden ser
    relevantes para Vigilancia.

    No modifica portalWyny.
    """

    return portal_fetch_all(
        """
        SELECT

            es.ID_PROCESS,
            es.ID_ESTATUS,

            LTRIM(
                RTRIM(
                    es.idEmpleado
                )
            ) AS idEmpleado,

            es.idTipoPermisoFk,

            es.fechaInicio,
            es.fechaFinal,
            es.fechaSolicitud,
            es.fechaConfirmacion,

            es.horaInicio,
            es.horaFinal,

            CAST(
                es.motivoPermiso
                AS varchar(max)
            ) AS motivoPermiso,

            ue.nombreCompleto,

            tp.permisoNombre

        FROM
            dbo.empleadosSolicitudes es

        LEFT JOIN
            dbo.usuarioEmpleado ue
                ON ue.idUsuarioFk
                    = es.idUsuarioFk

        LEFT JOIN
            dbo.tiposPermisos tp
                ON tp.ID_PROCESS
                    = es.idTipoPermisoFk

        WHERE
            es.ID_ESTATUS = 23

            AND es.fechaInicio IS NOT NULL

            AND ISNULL(
                es.fechaFinal,
                es.fechaInicio
            ) >= CAST(
                GETDATE()
                AS date
            )

            AND es.fechaSolicitud >=
                DATEFROMPARTS(
                    YEAR(GETDATE()),
                    1,
                    1
                )

        ORDER BY
            es.ID_PROCESS
        """
    )


def _datos_notificacion_vigilancia(
    solicitud: dict,
):

    solicitud_id = int(
        solicitud[
            "ID_PROCESS"
        ]
    )

    numero_empleado = _texto(
        solicitud.get(
            "idEmpleado"
        )
    )

    nombre = (
        _texto(
            solicitud.get(
                "nombreCompleto"
            )
        )
        or (
            "Empleado "
            + numero_empleado
        )
    )

    tipo_id = int(
        solicitud.get(
            "idTipoPermisoFk"
        )
        or 0
    )

    permiso_nombre = _texto(
        solicitud.get(
            "permisoNombre"
        )
    )

    hora_inicio = _hora_permiso(
        solicitud.get(
            "horaInicio"
        )
    )

    hora_final = _hora_permiso(
        solicitud.get(
            "horaFinal"
        )
    )


    if tipo_id == 1:

        icono = "🏖️"

        permiso_nombre = (
            "VACACIONES"
        )

    elif (
        hora_inicio
        or hora_final
    ):

        icono = "🚪"

        permiso_nombre = (
            permiso_nombre
            or "PERMISO PARCIAL"
        )

    else:

        icono = "📅"

        permiso_nombre = (
            permiso_nombre
            or "PERMISO"
        )


    if (
        hora_inicio
        or hora_final
    ):

        detalle = (
            "🕒 "
            + (
                hora_inicio
                or "--:--"
            )
            + " → "
            + (
                hora_final
                or "--:--"
            )
        )

    else:

        fecha_inicio = _fecha_texto(
            solicitud.get(
                "fechaInicio"
            )
        )

        fecha_final = _fecha_texto(
            solicitud.get(
                "fechaFinal"
            )
        )

        if (
            fecha_final
            and fecha_final != "-"
            and fecha_final
                != fecha_inicio
        ):

            detalle = (
                "📅 "
                + fecha_inicio
                + " → "
                + fecha_final
            )

        else:

            detalle = (
                "📅 "
                + fecha_inicio
            )


    body = (
        f"{numero_empleado} - {nombre}\n"
        f"{icono} {permiso_nombre.upper()}\n"
        f"{detalle}"
    )


    return {
        "title":
            "🛡 NOVA · Permiso autorizado",

        "body":
            body,

        "url":
            (
                "/vigilancia/movimientos"
                + "?fecha="
                + _fecha_iso(
                    solicitud.get(
                        "fechaInicio"
                    )
                )
                + "&buscar="
                + numero_empleado
            ),

        "tag":
            (
                "nova-vigilancia-permiso-"
                + str(
                    solicitud_id
                )
            ),
    }


def _crear_baseline_vigilancia(
    solicitudes: list,
):

    total = 0

    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        key = _vigilancia_event_key(
            solicitud_id
        )


        if notification_event_exists(
            key
        ):
            continue


        remember_notification_event(
            event_key=key,

            event_type=(
                "VIGILANCIA_PERMISO_BASELINE"
            ),

            recipient_employee=(
                "VIGILANCIA_BASELINE"
            ),

            source_id=str(
                solicitud_id
            ),

            sent=False,
        )

        total += 1


    set_notification_meta(
        VIGILANCIA_PERMISOS_BASELINE_KEY,
        "1",
    )


    print(
        "[NOVA PUSH] "
        "Baseline de Vigilancia creado: "
        f"{total} permiso(s)."
    )


    return total


def check_vigilancia_permission_notifications():

    solicitudes = (
        _obtener_permisos_autorizados_vigilancia()
    )


    baseline = get_notification_meta(
        VIGILANCIA_PERMISOS_BASELINE_KEY
    )


    if baseline != "1":

        total = (
            _crear_baseline_vigilancia(
                solicitudes
            )
        )

        return {
            "ok": True,
            "baseline_created":
                True,
            "baseline_requests":
                total,
            "sent":
                0,
        }


    destinatarios = (
        _obtener_destinatarios_vigilancia()
    )


    resultado = {
        "ok": True,
        "baseline_created":
            False,
        "checked":
            len(
                solicitudes
            ),
        "recipients":
            len(
                destinatarios
            ),
        "new":
            0,
        "sent":
            0,
        "without_device":
            0,
        "failed":
            0,
    }


    for solicitud in solicitudes:

        solicitud_id = int(
            solicitud[
                "ID_PROCESS"
            ]
        )

        key = _vigilancia_event_key(
            solicitud_id
        )


        if notification_event_exists(
            key
        ):
            continue


        resultado[
            "new"
        ] += 1


        if not destinatarios:

            resultado[
                "without_device"
            ] += 1

            continue


        datos = (
            _datos_notificacion_vigilancia(
                solicitud
            )
        )


        enviados = 0
        dispositivos = 0
        fallos = 0


        for destinatario in destinatarios:

            numero_vigilancia = _texto(
                destinatario.get(
                    "numero_empleado"
                )
            )


            if not numero_vigilancia:
                continue


            envio = send_to_employee(
                numero_vigilancia,

                title=datos[
                    "title"
                ],

                body=datos[
                    "body"
                ],

                url=datos[
                    "url"
                ],

                tag=datos[
                    "tag"
                ],
            )


            enviados += int(
                envio.get(
                    "sent",
                    0,
                )
                or 0
            )

            dispositivos += int(
                envio.get(
                    "total",
                    0,
                )
                or 0
            )


            if (
                int(
                    envio.get(
                        "total",
                        0,
                    )
                    or 0
                ) > 0
                and int(
                    envio.get(
                        "sent",
                        0,
                    )
                    or 0
                ) == 0
            ):

                fallos += 1


        if enviados > 0:

            remember_notification_event(
                event_key=key,

                event_type=(
                    "VIGILANCIA_PERMISO_AUTORIZADO"
                ),

                recipient_employee=(
                    "VIGILANCIA"
                ),

                source_id=str(
                    solicitud_id
                ),

                sent=True,
            )


            resultado[
                "sent"
            ] += enviados


            print(
                "[NOVA PUSH] "
                f"Permiso #{solicitud_id} "
                "notificado a Vigilancia "
                f"({enviados} envío(s))."
            )


        elif dispositivos == 0:

            # No registramos el evento.
            #
            # Si un integrante de Vigilancia activa
            # sus notificaciones después, el watcher
            # podrá volver a intentarlo mientras el
            # permiso siga siendo relevante.
            resultado[
                "without_device"
            ] += 1


        else:

            resultado[
                "failed"
            ] += max(
                fallos,
                1,
            )


    return resultado


def test_vigilancia_permission_notification(
    solicitud_id: int,
    numero_vigilancia: str,
):

    """
    Envía una prueba controlada a un solo empleado
    de Vigilancia.

    NO marca el permiso real como notificado.
    NO modifica portalWyny ni NominaInteligente.
    """

    solicitud = (
        _obtener_solicitud_resuelta(
            int(
                solicitud_id
            )
        )
    )


    if (
        not solicitud
        or int(
            solicitud.get(
                "ID_ESTATUS"
            )
            or 0
        ) != 23
    ):

        return {
            "ok": False,
            "error": (
                "La solicitud no existe "
                "o no está autorizada."
            ),
        }


    numero_vigilancia = _texto(
        numero_vigilancia
    )


    if not numero_vigilancia:

        return {
            "ok": False,
            "error": (
                "Falta el número de empleado "
                "de Vigilancia."
            ),
        }


    datos = (
        _datos_notificacion_vigilancia(
            solicitud
        )
    )


    envio = send_to_employee(
        numero_vigilancia,

        title=(
            "🧪 PRUEBA · "
            + datos[
                "title"
            ]
        ),

        body=datos[
            "body"
        ],

        url=datos[
            "url"
        ],

        tag=(
            "nova-prueba-vigilancia-"
            + str(
                solicitud_id
            )
        ),
    )


    return {
        "ok":
            int(
                envio.get(
                    "sent",
                    0,
                )
                or 0
            ) > 0,

        "solicitud":
            int(
                solicitud_id
            ),

        "vigilancia":
            numero_vigilancia,

        "envio":
            envio,
    }


# ============================================================
# HILO DE MONITOREO
# ============================================================

def _watch_loop():

    time.sleep(
        5
    )


    while True:

        # ====================================================
        # SOLICITUDES → GERENTES
        # ====================================================

        try:

            resultado_permisos = (
                check_permission_notifications()
            )


            if (
                resultado_permisos.get(
                    "new",
                    0,
                )
                or resultado_permisos.get(
                    "sent",
                    0,
                )
            ):

                print(
                    "[NOVA PUSH] "
                    "Revisión solicitudes:",
                    resultado_permisos,
                )


        except Exception:

            logger.exception(
                "Error revisando "
                "solicitudes para Web Push."
            )

        # ====================================================
        # AUTORIZACIÓN / RECHAZO → EMPLEADO
        # ====================================================

        try:

            resultado_respuestas = (
                check_employee_request_notifications()
            )


            if (
                resultado_respuestas.get(
                    "new",
                    0,
                )
                or resultado_respuestas.get(
                    "sent",
                    0,
                )
            ):

                print(
                    "[NOVA PUSH] "
                    "Revisión respuestas:",
                    resultado_respuestas,
                )


        except Exception:

            logger.exception(
                "Error revisando "
                "autorizaciones/rechazos "
                "para Web Push."
            )        


        # ====================================================
        # PERMISOS AUTORIZADOS → VIGILANCIA
        # ====================================================

        try:

            resultado_vigilancia = (
                check_vigilancia_permission_notifications()
            )


            if (
                resultado_vigilancia.get(
                    "new",
                    0,
                )
                or resultado_vigilancia.get(
                    "sent",
                    0,
                )
            ):

                print(
                    "[NOVA PUSH] "
                    "Revisión Vigilancia:",
                    resultado_vigilancia,
                )


        except Exception:

            logger.exception(
                "Error revisando "
                "permisos autorizados para "
                "Vigilancia Web Push."
            )


        # ====================================================
        # CHECADAS → CADA EMPLEADO
        # ====================================================

        try:

            resultado_checadas = (
                check_attendance_notifications()
            )


            if (
                resultado_checadas.get(
                    "entries_sent",
                    0,
                )
                or resultado_checadas.get(
                    "exits_sent",
                    0,
                )
            ):

                print(
                    "[NOVA PUSH] "
                    "Revisión checadas:",
                    resultado_checadas,
                )


        except Exception:

            logger.exception(
                "Error revisando "
                "checadas para Web Push."
            )


        time.sleep(
            CHECK_SECONDS
        )


def start_notification_watcher():

    global _started


    with _start_lock:

        if _started:
            return


        _started = True


        thread = threading.Thread(
            target=_watch_loop,
            name=(
                "nova-notification-watcher"
            ),
            daemon=True,
        )


        thread.start()


        print(
            "[NOVA PUSH] "
            "Watcher iniciado. "
            f"Intervalo: {CHECK_SECONDS}s"
        )