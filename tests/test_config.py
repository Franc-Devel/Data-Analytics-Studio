"""
Pruebas unitarias para el módulo de configuración por entorno (finance_app/config.py).
"""

import os
from pathlib import Path
from finance_app.config import AppConfig, get_config


def test_default_config_loading():
    cfg = get_config(reload=True)
    assert cfg is not None
    assert isinstance(cfg.base_dir, Path)
    assert cfg.app_env in ("development", "dev", "testing", "test", "production", "prod")
    assert cfg.log_level in ("DEBUG", "INFO", "WARNING", "ERROR")
    assert cfg.max_backups_retained > 0


def test_environment_detection():
    cfg_dev = AppConfig(app_env="development")
    assert cfg_dev.is_development is True
    assert cfg_dev.is_production is False
    assert cfg_dev.is_testing is False

    cfg_prod = AppConfig(app_env="production")
    assert cfg_prod.is_production is True
    assert cfg_prod.is_development is False

    cfg_test = AppConfig(app_env="testing")
    assert cfg_test.is_testing is True


def test_path_resolution(tmp_path):
    sample_file = tmp_path / "custom_leads.xlsx"
    sample_file.write_text("dummy")

    cfg = AppConfig(base_dir=tmp_path)
    # Ruta personalizada existente
    resolved = cfg.resolve_leads_path(sample_file)
    assert resolved == sample_file

    # Fallback automático a sample o configurado
    fallback = cfg.resolve_leads_path()
    assert isinstance(fallback, Path)
