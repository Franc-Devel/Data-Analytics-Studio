"""
Nexo Analytics - Sistema de Logging Centralizado
Configura rotación de archivos de log y salida en consola estructurada.
"""

from __future__ import annotations
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from finance_app.config import get_config

_INITIALIZED = False


def setup_logging(
    log_level: Optional[str] = None,
    log_dir: Optional[Path | str] = None,
    log_file_name: Optional[str] = None,
    force: bool = False,
) -> None:
    """Inicializa la configuración de logging del sistema."""
    global _INITIALIZED
    
    if _INITIALIZED and not force and log_dir is None:
        return

    cfg = get_config()
    level_str = (log_level or cfg.log_level).upper()
    level = getattr(logging, level_str, logging.INFO)
    
    target_log_dir = Path(log_dir) if log_dir else cfg.get_absolute_path(cfg.log_dir)
    target_log_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = target_log_dir / (log_file_name or cfg.log_file_name)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Formato de log profesional
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Si es forzado o reconfigurado con ruta específica, remover FileHandlers previos
    if force or log_dir is not None:
        for h in list(root_logger.handlers):
            if isinstance(h, (RotatingFileHandler, logging.FileHandler)):
                root_logger.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

    # 1. Rotating File Handler
    try:
        file_handler = RotatingFileHandler(
            filename=str(target_file),
            maxBytes=cfg.log_max_bytes,
            backupCount=cfg.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"No se pudo inicializar FileHandler de logs: {e}\n")
    
    # 2. Console Handler (solo una vez)
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, (RotatingFileHandler, logging.FileHandler)) for h in root_logger.handlers)
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger configurado con el espacio de nombres dado."""
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
