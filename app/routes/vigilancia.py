from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.database import engine

router = APIRouter()

templates = None


def set_templates(tmpl):
    global templates
    templates = tmpl

def tiene_acceso_vigilancia(roles: list[str]) -> bool:
    """
    Acceso al módulo de Vigilancia.
    """
    return any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "VIGILANCIA"]
    )


def validar_acceso_vigilancia(request: Request):
    usuario_id = request.session.get("usuario_id")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    if not tiene_acceso_vigilancia(roles):
        return RedirectResponse(
            url="/home",
            status_code=303
        )

    return None    


@router.get("/vigilancia/movimientos")
def vigilancia_movimientos(
    request: Request,
    fecha: str = Query(default_factory=lambda: date.today().isoformat()),
    buscar: str = Query(""),
):
    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    buscar_like = f"%{buscar.strip()}%"

    sql_empleados = text("""
        SELECT TOP 30
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            entrada_esperada,
            salida_esperada,
            checada_entrada_valida,
            checada_salida_valida,
            estatus_ejecutivo,
            semaforo,
            tipo_permiso,
            tipo_permiso AS permiso_nombre,
            goce_sueldo,
            permiso_inicio,
            permiso_fin,
            observacion_ejecutiva
        FROM dbo.vw_ni_vigilancia_empleado_dia
        WHERE fecha_operativa = :fecha
          AND (
                :buscar = ''
             OR numero_empleado LIKE :buscar_like
             OR nombre_completo LIKE :buscar_like
          )
        ORDER BY nombre_completo
    """)

    sql_movimientos = text("""
        SELECT TOP 100
            id,
            fecha_operativa,
            fecha_hora_evento,
            numero_empleado,
            nombre_completo,
            departamento,
            tipo_movimiento,
            motivo,
            tipo_permiso AS permiso_nombre,
            permiso_inicio,
            permiso_fin,
            observaciones,
            capturado_por,
            estatus
        FROM dbo.ni_vigilancia_movimientos_personal
        WHERE fecha_operativa = :fecha
        ORDER BY fecha_hora_evento DESC
    """)

    with engine.begin() as conn:
        empleados = conn.execute(
            sql_empleados,
            {"fecha": fecha, "buscar": buscar.strip(), "buscar_like": buscar_like},
        ).mappings().all()

        movimientos = conn.execute(sql_movimientos, {"fecha": fecha}).mappings().all()

    return templates.TemplateResponse(
        "vigilancia_movimientos.html",
        {
            "request": request,
            "fecha": fecha,
            "buscar": buscar,
            "empleados": empleados,
            "movimientos": movimientos,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
        },
    )


@router.post("/vigilancia/movimientos/registrar")
def registrar_movimiento_vigilancia(
    request: Request,
    fecha_operativa: str = Form(...),
    numero_empleado: str = Form(...),
    tipo_movimiento: str = Form(...),
    motivo: str = Form(""),
    observaciones: str = Form(""),
):
    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    sql_base = text("""
        SELECT TOP 1
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            entrada_esperada,
            salida_esperada,
            tipo_permiso,
            permiso_inicio,
            permiso_fin
        FROM dbo.vw_ni_vigilancia_empleado_dia
        WHERE fecha_operativa = :fecha_operativa
          AND numero_empleado = :numero_empleado
    """)

    sql_insert = text("""
        INSERT INTO dbo.ni_vigilancia_movimientos_personal (
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            tipo_movimiento,
            motivo,
            solicitud_id,
            tipo_permiso,
            permiso_inicio,
            permiso_fin,
            entrada_esperada,
            salida_esperada,
            observaciones,
            capturado_por
        )
        VALUES (
            :fecha_operativa,
            :numero_empleado,
            :nombre_completo,
            :departamento,
            :tipo_movimiento,
            :motivo,
            NULL,
            :tipo_permiso,
            :permiso_inicio,
            :permiso_fin,
            :entrada_esperada,
            :salida_esperada,
            :observaciones,
            :capturado_por
        )
    """)

    with engine.begin() as conn:
        empleado = conn.execute(
            sql_base,
            {"fecha_operativa": fecha_operativa, "numero_empleado": numero_empleado},
        ).mappings().first()

        if empleado:
            params = dict(empleado)
        else:
            params = {
                "fecha_operativa": fecha_operativa,
                "numero_empleado": numero_empleado,
                "nombre_completo": None,
                "departamento": None,
                "entrada_esperada": None,
                "salida_esperada": None,
                "tipo_permiso": None,
                "permiso_inicio": None,
                "permiso_fin": None,
            }

        params.update(
            {
                "tipo_movimiento": tipo_movimiento,
                "motivo": motivo,
                "observaciones": observaciones,
                "capturado_por": login_user,
            }
        )

        conn.execute(sql_insert, params)

    return RedirectResponse(
        url=f"/vigilancia/movimientos?fecha={fecha_operativa}",
        status_code=303,
    )


@router.get("/vigilancia/evento-colectivo")
def vigilancia_evento_colectivo(
    request: Request,
    fecha: str = Query(default_factory=lambda: date.today().isoformat()),
    evento_id: int | None = Query(None),
):
    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo

    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado_sesion = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    sql_eventos = text("""
        SELECT TOP 30
            id,
            fecha_operativa,
            fecha_hora_evento,
            tipo_evento,
            tipo_movimiento,
            motivo,
            descripcion,
            capturado_por,
            estatus
        FROM dbo.ni_vigilancia_eventos_colectivos
        WHERE fecha_operativa = :fecha
        ORDER BY id DESC
    """)

    sql_evento_actual = text("""
        SELECT TOP 1
            id,
            fecha_operativa,
            fecha_hora_evento,
            tipo_evento,
            tipo_movimiento,
            motivo,
            descripcion,
            capturado_por,
            estatus
        FROM dbo.ni_vigilancia_eventos_colectivos
        WHERE id = :evento_id
    """)

    sql_detalle = text("""
        SELECT
            d.id,
            d.evento_colectivo_id,
            d.fecha_operativa,
            d.numero_empleado,
            d.nombre_completo,
            d.departamento,
            d.entrada_esperada,
            d.salida_esperada,
            d.checada_entrada_valida,
            d.checada_salida_valida
        FROM dbo.ni_vigilancia_eventos_colectivos_detalle d
        WHERE d.evento_colectivo_id = :evento_id
        ORDER BY d.id DESC
    """)

    with engine.begin() as conn:
        eventos = conn.execute(sql_eventos, {"fecha": fecha}).mappings().all()

        evento_actual = None
        detalle = []

        if evento_id:
            evento_actual = conn.execute(
                sql_evento_actual,
                {"evento_id": evento_id},
            ).mappings().first()

            detalle = conn.execute(
                sql_detalle,
                {"evento_id": evento_id},
            ).mappings().all()

    return templates.TemplateResponse(
        "vigilancia_evento_colectivo.html",
        {
            "request": request,
            "fecha": fecha,
            "evento_id": evento_id,
            "eventos": eventos,
            "evento_actual": evento_actual,
            "detalle": detalle,
            "login_user": login_user,
            "nombre_usuario": nombre_usuario,
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
        },
    )


@router.post("/vigilancia/evento-colectivo/crear")
def crear_evento_colectivo(
    request: Request,
    fecha_operativa: str = Form(...),
    tipo_evento: str = Form(...),
    tipo_movimiento: str = Form(...),
    motivo: str = Form(...),
    descripcion: str = Form(""),
):

    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    sql_insert = text("""
        INSERT INTO dbo.ni_vigilancia_eventos_colectivos (
            fecha_operativa,
            tipo_evento,
            tipo_movimiento,
            motivo,
            descripcion,
            capturado_por
        )
        OUTPUT INSERTED.id
        VALUES (
            :fecha_operativa,
            :tipo_evento,
            :tipo_movimiento,
            :motivo,
            :descripcion,
            :capturado_por
        )
    """)

    with engine.begin() as conn:
        evento_id = conn.execute(
            sql_insert,
            {
                "fecha_operativa": fecha_operativa,
                "tipo_evento": tipo_evento,
                "tipo_movimiento": tipo_movimiento,
                "motivo": motivo,
                "descripcion": descripcion,
                "capturado_por": login_user,
            },
        ).scalar()

    return RedirectResponse(
        url=f"/vigilancia/evento-colectivo?fecha={fecha_operativa}&evento_id={evento_id}",
        status_code=303,
    )


@router.post("/vigilancia/evento-colectivo/agregar-empleado")
def agregar_empleado_evento_colectivo(
    request: Request,
    evento_id: int = Form(...),
    fecha_operativa: str = Form(...),
    numero_empleado: str = Form(...),
):

    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    numero_empleado = numero_empleado.strip()

    sql_empleado = text("""
        SELECT TOP 1
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            entrada_esperada,
            salida_esperada,
            checada_entrada_valida,
            checada_salida_valida
        FROM dbo.vw_ni_vigilancia_empleado_dia
        WHERE fecha_operativa = :fecha_operativa
          AND numero_empleado = :numero_empleado
    """)

    sql_insert_detalle = text("""
        IF NOT EXISTS (
            SELECT 1
            FROM dbo.ni_vigilancia_eventos_colectivos_detalle
            WHERE evento_colectivo_id = :evento_id
              AND numero_empleado = :numero_empleado
        )
        BEGIN
            INSERT INTO dbo.ni_vigilancia_eventos_colectivos_detalle (
                evento_colectivo_id,
                fecha_operativa,
                numero_empleado,
                nombre_completo,
                departamento,
                entrada_esperada,
                salida_esperada,
                checada_entrada_valida,
                checada_salida_valida
            )
            VALUES (
                :evento_id,
                :fecha_operativa,
                :numero_empleado,
                :nombre_completo,
                :departamento,
                :entrada_esperada,
                :salida_esperada,
                :checada_entrada_valida,
                :checada_salida_valida
            )
        END
    """)

    with engine.begin() as conn:
        empleado = conn.execute(
            sql_empleado,
            {"fecha_operativa": fecha_operativa, "numero_empleado": numero_empleado},
        ).mappings().first()

        if empleado:
            params = dict(empleado)
        else:
            params = {
                "fecha_operativa": fecha_operativa,
                "numero_empleado": numero_empleado,
                "nombre_completo": None,
                "departamento": None,
                "entrada_esperada": None,
                "salida_esperada": None,
                "checada_entrada_valida": None,
                "checada_salida_valida": None,
            }

        params.update({"evento_id": evento_id})
        conn.execute(sql_insert_detalle, params)

    return RedirectResponse(
        url=f"/vigilancia/evento-colectivo?fecha={fecha_operativa}&evento_id={evento_id}",
        status_code=303,
    )


@router.post("/vigilancia/evento-colectivo/registrar-todos")
def registrar_todos_evento_colectivo(
    request: Request,
    evento_id: int = Form(...),
    fecha_operativa: str = Form(...),
):

    bloqueo = validar_acceso_vigilancia(request)

    if bloqueo:
        return bloqueo    
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    sql_evento = text("""
        SELECT TOP 1
            id,
            fecha_operativa,
            tipo_evento,
            tipo_movimiento,
            motivo,
            descripcion
        FROM dbo.ni_vigilancia_eventos_colectivos
        WHERE id = :evento_id
    """)

    sql_insert_movimientos = text("""
        INSERT INTO dbo.ni_vigilancia_movimientos_personal (
            fecha_operativa,
            numero_empleado,
            nombre_completo,
            departamento,
            tipo_movimiento,
            motivo,
            observaciones,
            capturado_por,
            origen,
            estatus
        )
        SELECT
            d.fecha_operativa,
            d.numero_empleado,
            d.nombre_completo,
            d.departamento,
            e.tipo_movimiento,
            e.motivo,
            CONCAT('Evento colectivo #', e.id, ' - ', ISNULL(e.descripcion, '')),
            :capturado_por,
            'VIGILANCIA_COLECTIVO',
            'REGISTRADO'
        FROM dbo.ni_vigilancia_eventos_colectivos_detalle d
        INNER JOIN dbo.ni_vigilancia_eventos_colectivos e
            ON e.id = d.evento_colectivo_id
        WHERE d.evento_colectivo_id = :evento_id
          AND NOT EXISTS (
                SELECT 1
                FROM dbo.ni_vigilancia_movimientos_personal m
                WHERE m.fecha_operativa = d.fecha_operativa
                  AND m.numero_empleado = d.numero_empleado
                  AND m.tipo_movimiento = e.tipo_movimiento
                  AND m.motivo = e.motivo
                  AND m.origen = 'VIGILANCIA_COLECTIVO'
          );
    """)

    sql_update = text("""
        UPDATE dbo.ni_vigilancia_eventos_colectivos
        SET estatus = 'APLICADO'
        WHERE id = :evento_id;
    """)

    with engine.begin() as conn:
        evento = conn.execute(sql_evento, {"evento_id": evento_id}).mappings().first()

        if evento:
            conn.execute(
                sql_insert_movimientos,
                {"evento_id": evento_id, "capturado_por": login_user},
            )
            conn.execute(sql_update, {"evento_id": evento_id})

    return RedirectResponse(
        url=f"/vigilancia/evento-colectivo?fecha={fecha_operativa}&evento_id={evento_id}",
        status_code=303,
    )
