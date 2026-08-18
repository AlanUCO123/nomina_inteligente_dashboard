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
# INTELISIS
# 192.168.39.11
#
# SOLO LECTURA DESDE NOVA
# ============================================================

INTELISIS_DB_SERVER = os.getenv(
    "INTELISIS_DB_SERVER",
    "192.168.39.11",
)

INTELISIS_DB_NAME = os.getenv(
    "INTELISIS_DB_NAME",
    "Intelisis",
)

INTELISIS_DB_USER = os.getenv(
    "INTELISIS_DB_USER"
)

INTELISIS_DB_PASSWORD = os.getenv(
    "INTELISIS_DB_PASSWORD"
)

INTELISIS_DB_AUTH_TYPE = os.getenv(
    "INTELISIS_DB_AUTH_TYPE",
    "sql",
)

INTELISIS_DB_DRIVER = os.getenv(
    "INTELISIS_DB_DRIVER",
    "ODBC Driver 17 for SQL Server",
)


# ============================================================
# CADENA DE CONEXIÓN
# ============================================================

if INTELISIS_DB_AUTH_TYPE.lower() == "windows":

    connection_string = (
        f"DRIVER={{{INTELISIS_DB_DRIVER}}};"
        f"SERVER={INTELISIS_DB_SERVER};"
        f"DATABASE={INTELISIS_DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )

else:

    connection_string = (
        f"DRIVER={{{INTELISIS_DB_DRIVER}}};"
        f"SERVER={INTELISIS_DB_SERVER};"
        f"DATABASE={INTELISIS_DB_NAME};"
        f"UID={INTELISIS_DB_USER};"
        f"PWD={INTELISIS_DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )


params = quote_plus(
    connection_string
)


intelisis_engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,
    pool_recycle=1800,
)


# ============================================================
# SOLO SELECT
# ============================================================

def intelisis_fetch_all(
    query: str,
    params_dict: dict | None = None,
):

    with intelisis_engine.connect() as conn:

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


def intelisis_fetch_one(
    query: str,
    params_dict: dict | None = None,
):

    with intelisis_engine.connect() as conn:

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