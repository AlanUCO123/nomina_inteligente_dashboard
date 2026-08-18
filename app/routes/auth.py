import hashlib
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from app.database import engine

router = APIRouter()
_templates = None

def set_templates(templates):
    global _templates
    _templates = templates

@router.get("/login")
def login_form(request: Request):
    return _templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })

@router.post("/login")
async def login_post(request: Request):
    form_data = await request.form()
    login_user = form_data.get("login_user", "").strip()
    password = form_data.get("password", "")
    
    sql = text("""
        SELECT
            id AS usuario_id,
            login_user,
            nombre_usuario,
            numero_empleado,
            password_hash,
            activo,
            requiere_cambio_password
        FROM ni_usuarios
        WHERE login_user = :login_user
          AND activo = 1
    """)
    
    roles_sql = text("""
        SELECT r.codigo
        FROM ni_usuario_roles ur
        INNER JOIN ni_roles r
            ON r.id = ur.rol_id
        WHERE ur.usuario_id = :usuario_id
          AND ur.activo = 1
          AND r.activo = 1
    """)
    
    with engine.begin() as conn:
        user = conn.execute(sql, {"login_user": login_user}).mappings().first()
        
        if not user:
            return _templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Usuario o contraseña incorrectos."
            })
        
        if not user["password_hash"]:
            return _templates.TemplateResponse("login.html", {
                "request": request,
                "error": "El usuario no tiene contraseña configurada."
            })
        
        # Verificar contraseña con SHA256
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user["password_hash"]:
            return _templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Usuario o contraseña incorrectos."
            })
        
        # Obtener roles
        roles = conn.execute(
            roles_sql,
            {"usuario_id": user["usuario_id"]}
        ).scalars().all()
        
        # Actualizar último login
        conn.execute(
            text("""
                UPDATE ni_usuarios
                SET ultimo_login = GETDATE()
                WHERE id = :usuario_id
            """),
            {"usuario_id": user["usuario_id"]}
        )
    
    # Guardar sesión
    request.session["usuario_id"] = user["usuario_id"]
    request.session["login_user"] = user["login_user"]
    request.session["nombre_usuario"] = user["nombre_usuario"]
    request.session["numero_empleado"] = user["numero_empleado"]
    request.session["roles"] = roles if roles else []
    
    return RedirectResponse(url="/home", status_code=303)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/home")
def home(request: Request):
    usuario_id = request.session.get("usuario_id")

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    login_user = request.session.get("login_user")
    nombre_usuario = request.session.get("nombre_usuario")
    numero_empleado = request.session.get("numero_empleado")
    roles = request.session.get("roles", [])

    es_admin = any(
        rol in roles
        for rol in ["ADMIN", "SISTEMAS", "RH", "NOMINA"]
    )
    es_supervisor = "SUPERVISOR" in roles
    es_gerente = "GERENTE" in roles
    es_director = "DIRECTOR" in roles

    # ---------------------------------------------------------
    # Periodo actual: miércoles -> martes
    # ---------------------------------------------------------
    hoy = date.today()

    dias_desde_miercoles = (hoy.weekday() - 2) % 7
    fecha_inicio = hoy - timedelta(days=dias_desde_miercoles)
    fecha_fin = fecha_inicio + timedelta(days=6)

    params = {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "numero_empleado": numero_empleado,
    }

    # ---------------------------------------------------------
    # Alcance según rol
    # ---------------------------------------------------------
    if es_admin:
        where_scope = ""

    elif es_director:
        where_scope = """
            AND CAST(director AS VARCHAR(50))
                = CAST(:numero_empleado AS VARCHAR(50))
        """

    elif es_gerente:
        where_scope = """
            AND CAST(gerente AS VARCHAR(50))
                = CAST(:numero_empleado AS VARCHAR(50))
        """

    elif es_supervisor:
        where_scope = """
            AND CAST(reporta_a AS VARCHAR(50))
                = CAST(:numero_empleado AS VARCHAR(50))
        """

    else:
        where_scope = """
            AND CAST(numero_empleado AS VARCHAR(50))
                = CAST(:numero_empleado AS VARCHAR(50))
        """

    # ---------------------------------------------------------
    # KPIs actuales de asistencia
    # ---------------------------------------------------------
    sql_kpis = text(f"""
        SELECT
            COUNT(DISTINCT numero_empleado) AS empleados,

            SUM(
                CASE
                    WHEN estatus_asistencia = 'EN_TIEMPO'
                    THEN 1 ELSE 0
                END
            ) AS en_tiempo,

            SUM(
                CASE
                    WHEN estatus_asistencia = 'RETARDO'
                    THEN 1 ELSE 0
                END
            ) AS retardos,

            SUM(
                CASE
                    WHEN estatus_asistencia IN (
                        'FALTA',
                        'FALTA_ENTRADA'
                    )
                    THEN 1 ELSE 0
                END
            ) AS faltas,

            CAST(
                SUM(ISNULL(horas_extra_detectadas, 0))
                AS DECIMAL(10,2)
            ) AS horas_extra_detectadas

        FROM dbo.vw_ni_asistencia_checadas

        WHERE fecha_operativa
            BETWEEN :fecha_inicio AND :fecha_fin

        {where_scope}
    """)

    # ---------------------------------------------------------
    # Datos del usuario conectado
    # ---------------------------------------------------------
    sql_mis_datos = text("""
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
        FROM dbo.ni_empleados_maestro
        WHERE numero_empleado = :numero_empleado
    """)

    with engine.begin() as conn:
        kpis = conn.execute(
            sql_kpis,
            params
        ).mappings().first()

        mis_datos = conn.execute(
            sql_mis_datos,
            {"numero_empleado": numero_empleado}
        ).mappings().first()

    return _templates.TemplateResponse("home.html", {
        "request": request,
        "login_user": login_user,
        "nombre_usuario": nombre_usuario,
        "numero_empleado": numero_empleado,
        "roles": roles,

        "mis_datos": mis_datos,
        "kpis": kpis,

        "es_admin": es_admin,
        "es_supervisor": es_supervisor,
        "es_gerente": es_gerente,
        "es_director": es_director,

        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    })