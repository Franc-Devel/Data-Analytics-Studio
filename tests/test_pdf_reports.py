from pathlib import Path
import pytest
from finance_app.lead_intelligence import load_and_enrich_leads
from finance_app.commercial_analytics import load_and_analyze_commercial_data
from finance_app.pdf_reports import generate_executive_pdf_report, generate_monthly_pdf_report


def _get_test_paths():
    leads = Path("Leeds orden.xlsx")
    if not leads.exists():
        leads = Path("data/sample_leads.xlsx")
    comm = Path("Comercial.xlsx")
    if not comm.exists():
        comm = Path("data/sample_comercial.xlsx")
    return leads, comm


def test_generate_executive_pdf_report():
    leads_path, comm_path = _get_test_paths()

    if leads_path.exists() and comm_path.exists():
        sheets = load_and_enrich_leads(leads_path)
        commercial = load_and_analyze_commercial_data(comm_path)

        pdf_bytes = generate_executive_pdf_report(sheets, commercial)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 5000
        # PDF files start with %PDF-
        assert pdf_bytes.startswith(b"%PDF-")


def test_generate_monthly_pdf_report():
    leads_path, comm_path = _get_test_paths()

    if leads_path.exists() and comm_path.exists():
        sheets = load_and_enrich_leads(leads_path)
        commercial = load_and_analyze_commercial_data(comm_path)

        pdf_bytes = generate_monthly_pdf_report("Enero", sheets, commercial)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000
        assert pdf_bytes.startswith(b"%PDF-")
