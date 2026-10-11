import os
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent


def get_test_leads_path() -> Path:
    """Retorna la ruta al archivo de leads para pruebas (prioriza muestra sanitizada si no existe el original)."""
    p = ROOT_DIR / "Leeds orden.xlsx"
    if p.exists():
        return p
    sample = ROOT_DIR / "data" / "sample_leads.xlsx"
    if sample.exists():
        return sample
    return p


def get_test_commercial_path() -> Path:
    """Retorna la ruta al archivo comercial para pruebas (prioriza muestra sanitizada si no existe el original)."""
    p = ROOT_DIR / "Comercial.xlsx"
    if p.exists():
        return p
    sample = ROOT_DIR / "data" / "sample_comercial.xlsx"
    if sample.exists():
        return sample
    return p


@pytest.fixture
def leads_excel_path() -> Path:
    return get_test_leads_path()


@pytest.fixture
def commercial_excel_path() -> Path:
    return get_test_commercial_path()
