from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import create_engine, pool

# ---- IMPORTANTE: agregar la ruta de tu app ----
# Esto permite que Alembic importe tus modulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configuracion alembic.ini
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- Importar tu metadata (Base) ----
from app.config.database import (
    Base,
    DATABASE_URL,
    get_engine_kwargs,
    log_database_configuration,
)

config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

# Esto permite autogenerate detectar tus modelos
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo OFFLINE (sin conexion activa).
    """
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo ONLINE (con conexion activa).
    """
    log_database_configuration("alembic")
    connectable = create_engine(
        DATABASE_URL,
        **get_engine_kwargs(poolclass=pool.NullPool),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
