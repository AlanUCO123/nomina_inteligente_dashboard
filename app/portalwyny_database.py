import os
from urllib.parse import quote_plus
from decimal import Decimal
from datetime import datetime, date

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def _serialize_value(value):
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if value is None:
        return None

    return value


# ============================================================
# CONEXIÓN PORTAL WYNY
# ============================================================

PORTALWYNY_DB_SERVER = os.getenv(
    "PORTALWYNY_DB_SERVER",
    "192.168.39.206",
)

PORTALWYNY_DB_NAME = os.getenv(
    "PORTALWYNY_DB_NAME",
    "portalWyny",
)

PORTALWYNY_DB_USER = os.getenv(
    "PORTALWYNY_DB_USER"
)

PORTALWYNY_DB_PASSWORD = os.getenv(
    "PORTALWYNY_DB_PASSWORD"
)

PORTALWYNY_DB_AUTH_TYPE = os.getenv(
    "PORTALWYNY_DB_AUTH_TYPE",
    os.getenv("DB_AUTH_TYPE", "sql"),
)

PORTALWYNY_DB_DRIVER = os.getenv(
    "PORTALWYNY_DB_DRIVER",
    os.getenv(
        "DB_DRIVER",
        "ODBC Driver 17 for SQL Server",
    ),
)


if PORTALWYNY_DB_AUTH_TYPE.lower() == "windows":

    connection_string = (
        f"DRIVER={{{PORTALWYNY_DB_DRIVER}}};"
        f"SERVER={PORTALWYNY_DB_SERVER};"
        f"DATABASE={PORTALWYNY_DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )

else:

    connection_string = (
        f"DRIVER={{{PORTALWYNY_DB_DRIVER}}};"
        f"SERVER={PORTALWYNY_DB_SERVER};"
        f"DATABASE={PORTALWYNY_DB_NAME};"
        f"UID={PORTALWYNY_DB_USER};"
        f"PWD={PORTALWYNY_DB_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )


params = quote_plus(
    connection_string
)


portalwyny_engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,
    pool_recycle=1800,
)


# ============================================================
# FUNCIONES DE SOLO LECTURA
# ============================================================

def portal_fetch_all(
    query: str,
    params_dict: dict | None = None,
):

    with portalwyny_engine.connect() as conn:

        result = conn.execute(
            text(query),
            params_dict or {},
        )

        rows = result.mappings().all()

        return [
            {
                k: _serialize_value(v)
                for k, v in dict(row).items()
            }
            for row in rows
        ]


def portal_fetch_one(
    query: str,
    params_dict: dict | None = None,
):

    with portalwyny_engine.connect() as conn:

        result = conn.execute(
            text(query),
            params_dict or {},
        )

        row = result.mappings().first()

        if not row:
            return None

        return {
            k: _serialize_value(v)
            for k, v in dict(row).items()
        }