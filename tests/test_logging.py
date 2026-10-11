"""
Pruebas unitarias para el sistema de logging (finance_app/logging_config.py).
"""

import logging
from finance_app.logging_config import setup_logging, get_logger


def test_get_logger():
    logger = get_logger("test_module")
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_logging_to_file(tmp_path):
    log_dir = tmp_path / "test_logs"
    setup_logging(log_level="DEBUG", log_dir=log_dir, log_file_name="test.log")
    
    logger = get_logger("test_writer")
    test_msg = "Mensaje de prueba para logger automatizado"
    logger.info(test_msg)
    
    log_file = log_dir / "test.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content
