import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config.settings import settings

logger = logging.getLogger(__name__)

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _normalize_database_url(raw_url: str) -> URL:
    normalized = raw_url.strip()

    if normalized.startswith("postgres://"):
        normalized = f"postgresql+psycopg2://{normalized[len('postgres://'):]}"
    elif normalized.startswith("postgresql://"):
        normalized = f"postgresql+psycopg2://{normalized[len('postgresql://'):]}"

    url = make_url(normalized)

    if url.get_backend_name() == "postgresql" and url.drivername != "postgresql+psycopg2":
        url = url.set(drivername="postgresql+psycopg2")

    if url.get_backend_name() == "postgresql" and url.host not in LOCAL_DB_HOSTS:
        query = dict(url.query)
        if not query.get("sslmode"):
            query["sslmode"] = "require"
            url = url.set(query=query)

    return url


DATABASE_URL_OBJECT = _normalize_database_url(settings.DATABASE_URL)
DATABASE_URL = DATABASE_URL_OBJECT.render_as_string(hide_password=False)


def get_database_connect_args() -> dict[str, str]:
    if DATABASE_URL_OBJECT.get_backend_name() != "postgresql":
        return {}

    if DATABASE_URL_OBJECT.query.get("sslmode"):
        return {}

    if DATABASE_URL_OBJECT.host in LOCAL_DB_HOSTS:
        return {}

    return {"sslmode": "require"}


DATABASE_CONNECT_ARGS = get_database_connect_args()


def get_engine_kwargs(**overrides):
    kwargs = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    if DATABASE_CONNECT_ARGS:
        kwargs["connect_args"] = DATABASE_CONNECT_ARGS
    kwargs.update(overrides)
    return kwargs


def log_database_configuration(context: str) -> None:
    raw_database_url = os.getenv("DATABASE_URL")
    logger.warning(
        "[%s] DATABASE_URL env_present=%s effective_dialect=%s effective_driver=%s host=%s sslmode=%s",
        context,
        bool(raw_database_url and raw_database_url.strip()),
        DATABASE_URL_OBJECT.get_backend_name(),
        DATABASE_URL_OBJECT.get_driver_name(),
        DATABASE_URL_OBJECT.host or "<none>",
        DATABASE_URL_OBJECT.query.get("sslmode", "unset"),
    )


log_database_configuration("sqlalchemy-config")

engine = create_engine(DATABASE_URL, **get_engine_kwargs())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
