"""
Pruebas unitarias para la sincronización e importación/exportación bidireccional Excel <-> BD (finance_app/db/excel_sync.py).
"""

from pathlib import Path
from finance_app.db.session import get_db_session, reset_db
from finance_app.db.models import Customer, Opportunity
from finance_app.db.excel_sync import (
    import_leads_excel_to_db,
    import_commercial_excel_to_db,
    export_db_customers_to_dataframe,
)


def test_import_and_export_excel_sync():
    db_url = "sqlite://"
    reset_db(db_url)

    sample_leads = Path("data/sample_leads.xlsx")
    sample_comm = Path("data/sample_comercial.xlsx")

    if not sample_leads.exists() or not sample_comm.exists():
        return

    with get_db_session(db_url) as session:
        created, updated = import_leads_excel_to_db(session, sample_leads, user_actor="admin")
        assert created > 0
        assert session.query(Customer).count() == created

        # Re-importar (debe actualizar sin crear duplicados)
        created2, updated2 = import_leads_excel_to_db(session, sample_leads, user_actor="admin")
        assert created2 == 0
        assert updated2 > 0
        assert session.query(Customer).count() == created

        # Importar comercial
        opps = import_commercial_excel_to_db(session, sample_comm, user_actor="admin")
        assert opps > 0
        assert session.query(Opportunity).count() == opps

        # Exportar a DataFrame
        df_exp = export_db_customers_to_dataframe(session)
        assert len(df_exp) == session.query(Customer).count()
        assert "Nombre_Completo" in df_exp.columns
        assert "Telefono" in df_exp.columns
        assert "Lead_Score" in df_exp.columns
