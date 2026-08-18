from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DB_PATH = (
    ROOT_DIR
    / "data"
    / "nova_notifications.db"
)


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat(
            timespec="seconds"
        )
    )


def _connect():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=10,
    )

    conn.row_factory = (
        sqlite3.Row
    )

    return conn

def notification_event_exists(
    event_key: str,
) -> bool:

    with _connect() as conn:

        row = conn.execute(
            """
            SELECT
                event_key
            FROM
                notification_events
            WHERE
                event_key = ?
            LIMIT 1
            """,
            (
                str(event_key),
            ),
        ).fetchone()

    return row is not None


def remember_notification_event(
    *,
    event_key: str,
    event_type: str,
    recipient_employee: str,
    source_id: str | None = None,
    sent: bool = True,
):

    now = _utc_now()

    sent_at = (
        now
        if sent
        else None
    )

    with _connect() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO
                notification_events (
                    event_key,
                    event_type,
                    recipient_employee,
                    source_id,
                    created_at,
                    sent_at
                )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                str(event_key),
                str(event_type),
                str(recipient_employee),
                (
                    str(source_id)
                    if source_id is not None
                    else None
                ),
                now,
                sent_at,
            ),
        )


def get_notification_meta(
    meta_key: str,
) -> str | None:

    with _connect() as conn:

        row = conn.execute(
            """
            SELECT
                meta_value
            FROM
                notification_meta
            WHERE
                meta_key = ?
            LIMIT 1
            """,
            (
                str(meta_key),
            ),
        ).fetchone()

    if not row:
        return None

    return row["meta_value"]


def set_notification_meta(
    meta_key: str,
    meta_value: str,
):

    now = _utc_now()

    with _connect() as conn:

        conn.execute(
            """
            INSERT INTO
                notification_meta (
                    meta_key,
                    meta_value,
                    updated_at
                )
            VALUES (
                ?,
                ?,
                ?
            )

            ON CONFLICT(meta_key)
            DO UPDATE SET
                meta_value =
                    excluded.meta_value,

                updated_at =
                    excluded.updated_at
            """,
            (
                str(meta_key),
                str(meta_value),
                now,
            ),
        )

def init_notifications_db():
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS
            push_subscriptions (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                endpoint TEXT NOT NULL
                    UNIQUE,

                p256dh TEXT NOT NULL,

                auth TEXT NOT NULL,

                usuario_id INTEGER,

                numero_empleado TEXT
                    NOT NULL,

                login_user TEXT,

                nombre_usuario TEXT,

                device_name TEXT,

                user_agent TEXT,

                is_active INTEGER
                    NOT NULL
                    DEFAULT 1,

                created_at TEXT
                    NOT NULL,

                updated_at TEXT
                    NOT NULL,

                last_success_at TEXT,

                last_error TEXT
            );

            CREATE INDEX IF NOT EXISTS
            idx_push_employee_active
            ON push_subscriptions (
                numero_empleado,
                is_active
            );


            CREATE TABLE IF NOT EXISTS
            notification_events (
                event_key TEXT
                    PRIMARY KEY,

                event_type TEXT
                    NOT NULL,

                recipient_employee TEXT
                    NOT NULL,

                source_id TEXT,

                created_at TEXT
                    NOT NULL,

                sent_at TEXT
            );

            CREATE INDEX IF NOT EXISTS
            idx_notification_events_employee
            ON notification_events (
                recipient_employee,
                event_type
            );

            CREATE TABLE IF NOT EXISTS
            notification_meta (
                meta_key TEXT PRIMARY KEY,
                meta_value TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
            idx_notification_events_type
            ON notification_events (
                event_type
            );
            """
        )


def upsert_subscription(
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    usuario_id: int | None,
    numero_empleado: str,
    login_user: str,
    nombre_usuario: str,
    device_name: str,
    user_agent: str,
):
    now = _utc_now()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO
                push_subscriptions (
                    endpoint,
                    p256dh,
                    auth,
                    usuario_id,
                    numero_empleado,
                    login_user,
                    nombre_usuario,
                    device_name,
                    user_agent,
                    is_active,
                    created_at,
                    updated_at,
                    last_error
                )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                1,
                ?,
                ?,
                NULL
            )

            ON CONFLICT(endpoint)
            DO UPDATE SET
                p256dh =
                    excluded.p256dh,

                auth =
                    excluded.auth,

                usuario_id =
                    excluded.usuario_id,

                numero_empleado =
                    excluded.numero_empleado,

                login_user =
                    excluded.login_user,

                nombre_usuario =
                    excluded.nombre_usuario,

                device_name =
                    excluded.device_name,

                user_agent =
                    excluded.user_agent,

                is_active = 1,

                updated_at =
                    excluded.updated_at,

                last_error = NULL
            """,
            (
                endpoint,
                p256dh,
                auth,
                usuario_id,
                numero_empleado,
                login_user,
                nombre_usuario,
                device_name,
                user_agent,
                now,
                now,
            ),
        )


def get_subscription(
    *,
    endpoint: str,
    numero_empleado: str,
):
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                *
            FROM
                push_subscriptions
            WHERE
                endpoint = ?
                AND numero_empleado = ?
                AND is_active = 1
            LIMIT 1
            """,
            (
                endpoint,
                numero_empleado,
            ),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def list_active_subscriptions(
    numero_empleado: str,
):
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                *
            FROM
                push_subscriptions
            WHERE
                numero_empleado = ?
                AND is_active = 1
            ORDER BY
                id
            """,
            (
                numero_empleado,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def count_active_subscriptions(
    numero_empleado: str,
) -> int:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total
            FROM
                push_subscriptions
            WHERE
                numero_empleado = ?
                AND is_active = 1
            """,
            (
                numero_empleado,
            ),
        ).fetchone()

    return int(
        row["total"]
        if row
        else 0
    )


def deactivate_subscription(
    *,
    endpoint: str,
    numero_empleado: str,
):
    with _connect() as conn:
        conn.execute(
            """
            UPDATE
                push_subscriptions
            SET
                is_active = 0,
                updated_at = ?
            WHERE
                endpoint = ?
                AND numero_empleado = ?
            """,
            (
                _utc_now(),
                endpoint,
                numero_empleado,
            ),
        )


def mark_success(
    endpoint: str,
):
    with _connect() as conn:
        conn.execute(
            """
            UPDATE
                push_subscriptions
            SET
                last_success_at = ?,
                last_error = NULL,
                updated_at = ?
            WHERE
                endpoint = ?
            """,
            (
                _utc_now(),
                _utc_now(),
                endpoint,
            ),
        )


def mark_error(
    endpoint: str,
    error: str,
):
    with _connect() as conn:
        conn.execute(
            """
            UPDATE
                push_subscriptions
            SET
                last_error = ?,
                updated_at = ?
            WHERE
                endpoint = ?
            """,
            (
                str(error)[:1000],
                _utc_now(),
                endpoint,
            ),
        )


init_notifications_db()