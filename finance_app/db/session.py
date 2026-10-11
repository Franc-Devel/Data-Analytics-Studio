"""
Nexo Analytics - Gestión de Conexión y Sesiones de Base de Datos
Soporte dual nativo para PostgreSQL (producción) y SQLite (desarrollo/testing).
"""

from __future__ import annotations
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict, Any

from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("db.session")

Base = declarative_base()

_engines: Dict[str, Engine] = {}
_session_factories: Dict[str, sessionmaker[Session]] = {}


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Crea u obtiene el motor SQLAlchemy con configuración optimizada."""
    cfg = get_config()
    url = database_url or cfg.database_url

    if url in _engines:
        return _engines[url]

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        
        is_memory = ":memory:" in url
        if not is_memory and "///" in url:
            db_rel_path = url.split("///", 1)[1]
            db_abs_path = cfg.get_absolute_path(db_rel_path)
            db_abs_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{db_abs_path}"

        engine_kwargs: Dict[str, Any] = {
            "connect_args": connect_args,
            "echo": False,
            "future": True,
        }
        if is_memory:
            engine_kwargs["poolclass"] = StaticPool

        engine = create_engine(url, **engine_kwargs)

        # Habilitar WAL mode, busy_timeout y soporte de claves foráneas en SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    else:
        # PostgreSQL / MySQL
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
            future=True,
        )

    _engines[url] = engine
    return engine


def get_session_factory(database_url: Optional[str] = None) -> sessionmaker[Session]:
    """Obtiene la fábrica de sesiones de SQLAlchemy."""
    cfg = get_config()
    url = database_url or cfg.database_url

    if url in _session_factories:
        return _session_factories[url]

    engine = get_engine(url)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    _session_factories[url] = factory
    return factory


@contextmanager
def get_db_session(database_url: Optional[str] = None) -> Generator[Session, None, None]:
    """Context manager para obtener una sesión con commit y rollback automático."""
    factory = get_session_factory(database_url)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en transacción de BD: {e}", exc_info=True)
        raise
    finally:
        session.close()


def init_db(database_url: Optional[str] = None) -> None:
    """Inicializa el esquema de base de datos creando todas las tablas tras validar seguridad de producción."""
    cfg = get_config()
    cfg.validate_production_readiness()

    from finance_app.db.models import (
        User,
        Customer,
        CustomerSearchToken,
        Opportunity,
        Task,
        ActivityLog,
        AuditLog,
        AssignmentRule,
        WhatsAppQueueMessage,
        PendingCRMProposal,
    )
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    from finance_app.db.migrations import run_auto_migrations
    run_auto_migrations(engine)
    logger.info("Esquema de base de datos verificado e inicializado.")


def reset_db(database_url: Optional[str] = None) -> None:
    """Reinicia el esquema de base de datos borrando y recreando todas las tablas."""
    from finance_app.db.models import (
        User,
        Customer,
        CustomerSearchToken,
        Opportunity,
        Task,
        ActivityLog,
        AuditLog,
        AssignmentRule,
        WhatsAppQueueMessage,
        PendingCRMProposal,
    )
    engine = get_engine(database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Esquema de base de datos reiniciado limpiamente.")
