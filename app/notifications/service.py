from __future__ import annotations

import json
from pathlib import Path

from pywebpush import (
    WebPushException,
    webpush,
)

from app.notifications.repository import (
    deactivate_subscription,
    list_active_subscriptions,
    mark_error,
    mark_success,
)


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PRIVATE_KEY_PATH = (
    ROOT_DIR
    / "data"
    / "nova_vapid_private.pem"
)

PUBLIC_KEY_PATH = (
    ROOT_DIR
    / "data"
    / "nova_vapid_public.txt"
)

VAPID_SUBJECT = (
    "mailto:sistemas@wyny.mx"
)


def get_public_key() -> str:
    if not PUBLIC_KEY_PATH.exists():
        return ""

    return (
        PUBLIC_KEY_PATH
        .read_text(
            encoding="utf-8",
        )
        .strip()
    )


def push_is_configured() -> bool:
    return bool(
        PRIVATE_KEY_PATH.exists()
        and get_public_key()
    )


def _subscription_info(
    subscription: dict,
):
    return {
        "endpoint":
            subscription[
                "endpoint"
            ],

        "keys": {
            "p256dh":
                subscription[
                    "p256dh"
                ],

            "auth":
                subscription[
                    "auth"
                ],
        },
    }


def send_to_subscription(
    subscription: dict,
    *,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "nova",
    data_extra: dict | None = None,
):
    if not push_is_configured():
        raise RuntimeError(
            "Las llaves VAPID de NOVA "
            "no están configuradas."
        )

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "tag": tag,
    }

    if data_extra:
        payload.update(
            data_extra
        )

    endpoint = str(
        subscription[
            "endpoint"
        ]
    )

    try:
        webpush(
            subscription_info=(
                _subscription_info(
                    subscription
                )
            ),
            data=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            vapid_private_key=(
                str(
                    PRIVATE_KEY_PATH
                )
            ),
            vapid_claims={
                "sub":
                    VAPID_SUBJECT,
            },
            ttl=120,
        )

        mark_success(
            endpoint
        )

        return {
            "ok": True,
            "endpoint": endpoint,
        }

    except WebPushException as exc:
        mark_error(
            endpoint,
            str(exc),
        )

        response = getattr(
            exc,
            "response",
            None,
        )

        status_code = getattr(
            response,
            "status_code",
            None,
        )

        if status_code in (
            404,
            410,
        ):
            deactivate_subscription(
                endpoint=endpoint,
                numero_empleado=str(
                    subscription[
                        "numero_empleado"
                    ]
                ),
            )

        raise


def send_to_employee(
    numero_empleado: str,
    *,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "nova",
    data_extra: dict | None = None,
):
    subscriptions = (
        list_active_subscriptions(
            str(
                numero_empleado
            )
        )
    )

    result = {
        "total": len(
            subscriptions
        ),
        "sent": 0,
        "failed": 0,
        "errors": [],
    }

    for subscription in subscriptions:
        try:
            send_to_subscription(
                subscription,
                title=title,
                body=body,
                url=url,
                tag=tag,
                data_extra=data_extra,
            )

            result["sent"] += 1

        except Exception as exc:
            result["failed"] += 1

            result["errors"].append(
                str(exc)
            )

    return result