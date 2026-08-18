import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.notifications.watcher import (
    start_notification_watcher,
)

class CompatibleJinja2Templates(Jinja2Templates):
    """
    Permite utilizar tanto la sintaxis nueva como la antigua
    de TemplateResponse.
    """

    def TemplateResponse(self, *args, **kwargs):
        # Sintaxis antigua:
        # TemplateResponse("archivo.html", {"request": request, ...})
        if args and isinstance(args[0], str):
            name = args[0]

            context = (
                args[1]
                if len(args) > 1
                else kwargs.pop("context", {})
            )

            if not isinstance(context, dict):
                raise TypeError(
                    "El contexto de la plantilla debe ser un diccionario."
                )

            request = context.get("request")

            if request is None:
                raise RuntimeError(
                    "Falta 'request' en el contexto de la plantilla."
                )

            if len(args) > 2:
                kwargs.setdefault("status_code", args[2])

            return super().TemplateResponse(
                request=request,
                name=name,
                context=context,
                **kwargs
            )

        # Sintaxis nueva
        return super().TemplateResponse(*args, **kwargs)

from app.routes.dashboard import router as dashboard_router
from app.routes.horas_extra import router as horas_extra_router
from app.routes import he_control
from app.routes import auth
from app.routes import integraciones
from app.routes import asistencia
from app.routes import vigilancia
from app.routes import solicitudes
from app.routes import test_css
from app.routes import gerencia
from app.routes.notificaciones import (
    router as notificaciones_router,
)

app = FastAPI(
    title="NOVA Personal - Monitor Vivo de Asistencia",
    version="0.1.0",
)

@app.on_event("startup")
def iniciar_notificaciones_nova():

    start_notification_watcher()

# Agregar SessionMiddleware para gestión de sesiones
app.add_middleware(
    SessionMiddleware,
    secret_key="NOVA_PERSONAL_CAMBIAR_ESTA_LLAVE_2026",
    max_age=60 * 60 * 8  # 8 horas
)

# Configurar templates con ruta absoluta
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

templates = CompatibleJinja2Templates(
    directory=templates_dir
)

app.state.templates = templates

# Pasar templates a he_control router
he_control.set_templates(templates)

# Pasar templates a auth router
auth.set_templates(templates)

# Pasar templates a integraciones router
integraciones.set_templates(templates)

# Pasar templates a asistencia router
asistencia.set_templates(templates)

# Pasar templates a vigilancia router
vigilancia.set_templates(templates)
solicitudes.set_templates(templates)
gerencia.set_templates(templates)

# Configurar static files con ruta absoluta
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth.router)
app.include_router(dashboard_router)
app.include_router(horas_extra_router)
app.include_router(he_control.router)
app.include_router(integraciones.router)
app.include_router(asistencia.router)
app.include_router(vigilancia.router)
app.include_router(gerencia.router)
app.include_router(solicitudes.router)
app.include_router(test_css.router)
app.include_router(
    notificaciones_router
)
