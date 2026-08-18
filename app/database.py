import os
from urllib.parse import quote_plus
from decimal import Decimal
from datetime import datetime, date

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

def _serialize_value(value):
    """Convertir tipos no JSON serializables a tipos básicos"""
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif value is None:
        return None
    return value

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_AUTH_TYPE = os.getenv("DB_AUTH_TYPE", "sql")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

# Construir cadena de conexión según tipo de autenticación
if DB_AUTH_TYPE.lower() == "windows":
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
else:
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )

params = quote_plus(connection_string)

engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,
    fast_executemany=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def fetch_all(query: str, params_dict: dict | None = None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params_dict or {})
        rows = result.mappings().all()
        return [
            {k: _serialize_value(v) for k, v in dict(row).items()}
            for row in rows
        ]

def fetch_one(query: str, params_dict: dict | None = None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params_dict or {})
        row = result.mappings().first()
        if row:
            # Convertir a diccionario y serializar valores no JSON
            return {k: _serialize_value(v) for k, v in dict(row).items()}
        return None

def execute_sql(query: str, params_dict: dict | None = None):
    with engine.begin() as conn:
        conn.execute(text(query), params_dict or {})
