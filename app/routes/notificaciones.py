from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)

from fastapi.responses import (
    FileResponse,
    HTMLResponse,
)

from fastapi.templating import (
    Jinja2Templates,
)

from pydantic import BaseModel


from app.notifications.repository import (
    count_active_subscriptions,
    deactivate_subscription,
    get_subscription,
    upsert_subscription,
)

from app.notifications.service import (
    get_public_key,
    push_is_configured,
    send_to_subscription,
)


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

templates = Jinja2Templates(
    directory=str(
        ROOT_DIR
        / "app"
        / "templates"
    )
)

router = APIRouter()


class SubscriptionKeys(
    BaseModel
):
    p256dh: str
    auth: str


class BrowserSubscription(
    BaseModel
):
    endpoint: str
    keys: SubscriptionKeys


class SubscribePayload(
    BaseModel
):
    subscription: BrowserSubscription
    device_name: str = ""
    user_agent: str = ""


class EndpointPayload(
    BaseModel
):
    endpoint: str


def _identity(
    request: Request,
):
    usuario_id = (
        request.session.get(
            "usuario_id"
        )
    )

    login_user = str(
        request.session.get(
            "login_user"
        )
        or ""
    ).strip()

    numero_empleado = str(
        request.session.get(
            "numero_empleado"
        )
        or login_user
        or ""
    ).strip()

    nombre_usuario = str(
        request.session.get(
            "nombre_usuario"
        )
        or ""
    ).strip()

    roles = (
        request.session.get(
            "roles"
        )
        or []
    )

    if not numero_empleado:
        raise HTTPException(
            status_code=401,
            detail=(
                "Sesión no válida."
            ),
        )

    return {
        "usuario_id":
            usuario_id,

        "login_user":
            login_user,

        "numero_empleado":
            numero_empleado,

        "nombre_usuario":
            nombre_usuario,

        "roles":
            roles,
    }


@router.get(
    "/service-worker.js",
    include_in_schema=False,
)
def service_worker():
    return FileResponse(
        path=str(
            ROOT_DIR
            / "app"
            / "static"
            / "service-worker.js"
        ),
        media_type=(
            "application/javascript"
        ),
        headers={
            "Service-Worker-Allowed":
                "/",

            "Cache-Control":
                (
                    "no-cache, "
                    "no-store, "
                    "must-revalidate"
                ),
        },
    )


@router.get(
    "/notificaciones",
    response_class=HTMLResponse,
)
def notification_settings(
    request: Request,
):
    identity = _identity(
        request
    )

    total_devices = (
        count_active_subscriptions(
            identity[
                "numero_empleado"
            ]
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="notificaciones.html",
        context={
            "request":
                request,

            "login_user":
                identity[
                    "login_user"
                ],

            "nombre_usuario":
                identity[
                    "nombre_usuario"
                ],

            "numero_empleado":
                identity[
                    "numero_empleado"
                ],

            "roles":
                identity[
                    "roles"
                ],

            "push_configured":
                push_is_configured(),

            "vapid_public_key":
                get_public_key(),

            "registered_devices":
                total_devices,
        },
    )


@router.post(
    "/api/notificaciones/suscribir"
)
def subscribe(
    payload: SubscribePayload,
    request: Request,
):
    identity = _identity(
        request
    )

    if not push_is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Web Push no está "
                "configurado."
            ),
        )

    subscription = (
        payload.subscription
    )

    upsert_subscription(
        endpoint=(
            subscription.endpoint
        ),
        p256dh=(
            subscription
            .keys
            .p256dh
        ),
        auth=(
            subscription
            .keys
            .auth
        ),
        usuario_id=(
            identity[
                "usuario_id"
            ]
        ),
        numero_empleado=(
            identity[
                "numero_empleado"
            ]
        ),
        login_user=(
            identity[
                "login_user"
            ]
        ),
        nombre_usuario=(
            identity[
                "nombre_usuario"
            ]
        ),
        device_name=(
            payload.device_name
        ),
        user_agent=(
            payload.user_agent
        ),
    )

    return {
        "ok": True,
        "message": (
            "Dispositivo registrado "
            "correctamente."
        ),
    }


@router.post(
    "/api/notificaciones/desuscribir"
)
def unsubscribe(
    payload: EndpointPayload,
    request: Request,
):
    identity = _identity(
        request
    )

    deactivate_subscription(
        endpoint=(
            payload.endpoint
        ),
        numero_empleado=(
            identity[
                "numero_empleado"
            ]
        ),
    )

    return {
        "ok": True,
        "message": (
            "Notificaciones "
            "desactivadas."
        ),
    }


@router.post(
    "/api/notificaciones/prueba"
)
def test_notification(
    payload: EndpointPayload,
    request: Request,
):
    identity = _identity(
        request
    )

    subscription = (
        get_subscription(
            endpoint=(
                payload.endpoint
            ),
            numero_empleado=(
                identity[
                    "numero_empleado"
                ]
            ),
        )
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=(
                "Este dispositivo no "
                "está registrado para "
                "el usuario actual."
            ),
        )

    nombre = (
        identity[
            "nombre_usuario"
        ]
        or identity[
            "numero_empleado"
        ]
    )

    send_to_subscription(
        subscription,
        title=(
            "🔔 NOVA Personal"
        ),
        body=(
            f"Hola {nombre}. "
            "Las notificaciones "
            "de NOVA están funcionando "
            "correctamente."
        ),
        url="/",
        tag=(
            "nova-prueba-"
            + identity[
                "numero_empleado"
            ]
        ),
    )

    return {
        "ok": True,
        "message": (
            "Notificación enviada "
            "correctamente."
        ),
    }