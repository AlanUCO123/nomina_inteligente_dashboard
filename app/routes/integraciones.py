from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

router = APIRouter()

# Templates se obtiene de app.main
templates = None

def set_templates(tmpl):
    global templates
    templates = tmpl

def tiene_rol(roles: list[str], permitidos: list[str]) -> bool:
    return any(rol in roles for rol in permitidos)

@router.get("/empleados/mantenimiento")
def mantenimiento_empleados(request: Request):
    usuario_id = request.session.get("usuario_id")
    login_user = request.session.get("login_user")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    permitido = (
        login_user == "iracheta"
        or tiene_rol(roles, ["ADMIN", "SISTEMAS"])
    )

    if not permitido:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "mensaje": "No tienes permiso para acceder a Mantenimiento de Datos de Empleados.",
            "login_user": login_user,
            "nombre_usuario": request.session.get("nombre_usuario"),
            "numero_empleado": request.session.get("numero_empleado"),
            "roles": roles,
        })

    return RedirectResponse(
        url="http://192.168.39.28:8501/",
        status_code=302
    )

@router.get("/nomina/cambios-sueldo")
def cambios_sueldo(request: Request, empleado: str | None = None):
    usuario_id = request.session.get("usuario_id")
    numero_empleado_sesion = request.session.get("numero_empleado")
    login_user = request.session.get("login_user")
    roles = request.session.get("roles", [])

    if not usuario_id:
        return RedirectResponse(url="/login", status_code=303)

    permitido = tiene_rol(
        roles,
        ["GERENTE", "DIRECTOR", "RH", "NOMINA", "ADMIN", "SISTEMAS"]
    )

    if not permitido:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "mensaje": "No tienes permiso para acceder a Cambios de Sueldo.",
            "login_user": login_user,
            "nombre_usuario": request.session.get("nombre_usuario"),
            "numero_empleado": numero_empleado_sesion,
            "roles": roles,
        })

    es_admin = tiene_rol(roles, ["ADMIN", "SISTEMAS", "RH", "NOMINA"])

    empleado_destino = empleado or numero_empleado_sesion

    # Provisional:
    # Gerente o Director sin permiso admin solo abre su propio empleado,
    # salvo que después hagamos validación jerárquica.
    if not es_admin:
        empleado_destino = numero_empleado_sesion

    params = urlencode({
        "empleado": empleado_destino
    })

    url = f"http://192.168.39.28:8009/?{params}"

    return RedirectResponse(url=url, status_code=302)
