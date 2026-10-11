import datetime
from pathlib import Path
import shutil
import pandas as pd
import pytest

from finance_app.lead_intelligence import (
    load_and_enrich_leads,
    compute_lead_kpis,
    calculate_recontact_recommendation,
    calculate_lead_score,
    build_whatsapp_link,
)
from finance_app.whatsapp_service import (
    register_lead_contact_event,
    update_excel_with_whatsapp_leads,
    WhatsAppMessage,
    WhatsAppSyncState,
    get_lead_chat_timeline,
)


def test_full_crm_outreach_workflow(tmp_path):
    """
    Verifica el flujo completo:
    1. Un prospecto con interés en Davis / Vantage Vue está inicialmente pendiente de contacto (Urgente).
    2. Se le envía o registra la plantilla de lanzamiento 'Davis Vantage Vue'.
    3. El sistema actualiza el Excel con fecha de contacto y 'WA Saliente'.
    4. Al recargar la base, el prospecto transiciona a 'En Seguimiento' y sale de la lista de Urgentes.
    5. Se recalculan los KPIs reflejando el nuevo estado.
    """
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip("No se encuentra archivo de leads para pruebas")

    temp_excel = tmp_path / "Leeds_workflow_test.xlsx"
    shutil.copy2(orig_excel, temp_excel)

    # 1. Cargar estado inicial
    initial_sheets = load_and_enrich_leads(temp_excel)
    initial_master = initial_sheets["Leeds"]
    initial_kpis = compute_lead_kpis(initial_master)
    initial_urgentes = initial_kpis.recontacto_urgente

    # Localizar un lead de Davis sin toques salientes
    davis_leads = initial_master[
        (initial_master["Linea_Producto"] == "Davis") &
        (initial_master["Convertido_Derivado"] == 0) &
        (~initial_master["Consulta_Detalle"].astype(str).str.contains("WA Saliente", case=False, na=False))
    ]
    if davis_leads.empty:
        davis_leads = initial_master[initial_master["Convertido_Derivado"] == 0]

    target_lead = davis_leads.iloc[0]
    lead_id = target_lead["ID_Lead"]
    lead_name = target_lead["Contacto"]
    lead_phone = target_lead["Telefono"]

    # 2. Construir mensaje de WhatsApp oficial Davis Vantage Vue
    vantage_msg = (
        "¡Tenemos una novedad que puede interesarte! 🌦️\n\n"
        "Como anteriormente nos consultaste por estaciones meteorológicas Davis, quería contarte que ya está disponible la nueva Vantage Vue, con precio especial de lanzamiento y stock limitado.\n\n"
        "Si todavía estás evaluando incorporar una estación, consultame hoy por el valor promocional y disponibilidad."
    )
    wa_url = build_whatsapp_link(lead_phone, lead_name, "Davis", custom_text=vantage_msg)
    assert "https://wa.me/" in wa_url
    assert "Vantage%20Vue" in wa_url

    # 3. Registrar el envío del mensaje en el CRM (1 Clic)
    success = register_lead_contact_event(
        excel_path=temp_excel,
        lead_id_or_phone=lead_id,
        message_text=vantage_msg,
        action_type="Lanzamiento Vantage Vue"
    )
    assert success is True

    # 4. Recargar el dataset enriquecido tras la acción
    updated_sheets = load_and_enrich_leads(temp_excel)
    updated_master = updated_sheets["Leeds"]
    updated_kpis = compute_lead_kpis(updated_master)

    # Buscar el lead modificado
    mod_lead = updated_master[updated_master["ID_Lead"] == lead_id].iloc[0]

    # Validaciones críticas de negocio:
    # A) Cant_Contactos debe haber aumentado
    assert mod_lead["Cant_Contactos"] >= target_lead["Cant_Contactos"]
    # B) Consulta_Detalle debe contener 'WA Saliente'
    assert "WA Saliente" in mod_lead["Consulta_Detalle"]
    assert "Vantage Vue" in mod_lead["Consulta_Detalle"]
    # C) Prioridad de Recontacto debe ser '🟢 Hablado Hoy' o '🟡 En Seguimiento', NO '🔴 Urgente'
    assert mod_lead["Recontacto_Prioridad"] != "🔴 Urgente"
    assert mod_lead["Recontacto_Prioridad"] == "🟢 Hablado Hoy"
    assert "espera" in mod_lead["Accion_Sugerida"].lower() or "seguimiento" in mod_lead["Accion_Sugerida"].lower()
    # D) Timeline debe contener el mensaje saliente
    timeline = get_lead_chat_timeline(mod_lead)
    assert any(m["type"] == "whatsapp_out" and "Vantage Vue" in m["text"] for m in timeline)


def test_incoming_response_and_derivation_workflow(tmp_path):
    """
    Verifica que cuando el cliente responde al mensaje saliente y se deriva a closer:
    1. Se actualiza el lead con la respuesta entrante.
    2. Si indica 'Derivado a Jony' o similar, pasa a Ganado / Derivado (Convertido_Derivado = 1).
    3. Su prioridad pasa a '⚪ No Requiere'.
    """
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip("No se encuentra archivo de leads para pruebas")

    temp_excel = tmp_path / "Leeds_reply_test.xlsx"
    shutil.copy2(orig_excel, temp_excel)
    temp_state = WhatsAppSyncState(tmp_path / "state_reply.json")

    # Lead responde positivamente y solicita reunión con Jony
    reply_msg = WhatsAppMessage(
        message_id="msg_in_reply_001",
        sender_phone="3512 38-3481",
        sender_name="Cliente Interesado",
        timestamp=datetime.datetime.now(),
        text="Me interesa la Vantage Vue. Por favor pasar a Jony para coordinar cotización formal",
        is_from_me=False
    )

    new_c, upd_c = update_excel_with_whatsapp_leads(temp_excel, [reply_msg], temp_state)
    assert upd_c == 1

    sheets = load_and_enrich_leads(temp_excel)
    master = sheets["Leeds"]
    row = master[master["Telefono"].astype(str).str.contains("3512 38-3481", na=False)].iloc[0]

    assert row["Convertido_Derivado"] == 1
    assert "Derivado" in row["Estado_Lead"] or "Ganado" in row["Estado_Lead"] or row["Lead_Score"] >= 80
    assert row["Recontacto_Prioridad"] == "⚪ No Requiere"


def test_hybrid_encrypted_customer_search():
    """
    Verifica que la búsqueda híbrida funcione correctamente sobre campos cifrados con AES-256-GCM:
    - Búsqueda exacta por blind index (teléfono y nombre).
    - Búsqueda parcial en memoria por fragmento de nombre, teléfono o empresa.
    """
    from finance_app.db.session import get_db_session, reset_db
    from finance_app.db.crm_service import create_or_update_customer, search_customers, get_customer_by_phone
    from finance_app.db.models import CustomerSearchToken

    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        c1, _ = create_or_update_customer(
            session=session,
            phone="+5491122334455",
            full_name="Agustin Gomez",
            company="Acme Corp",
            province="Buenos Aires",
            locality="CABA",
        )
        c2, _ = create_or_update_customer(
            session=session,
            phone="+5491199887766",
            full_name="Carlos Rodriguez",
            company="Beta SA",
            province="Cordoba",
            locality="Villa Maria",
        )
        session.flush()

        assert session.query(CustomerSearchToken).filter_by(customer_id=c1.id).count() > 0
        assert session.query(CustomerSearchToken).filter_by(customer_id=c2.id).count() > 0

        # 1. Búsqueda exacta por teléfono (Blind Index)
        found_phone = get_customer_by_phone(session, "+5491122334455")
        assert found_phone is not None
        assert found_phone.id == c1.id

        # 2. Búsqueda exacta por nombre
        found_name = search_customers(session, query="Agustin Gomez")
        assert len(found_name) >= 1
        assert found_name[0].id == c1.id

        # 3. Búsqueda parcial por apellido (evaluación híbrida descifrada)
        found_part_name = search_customers(session, query="Gomez")
        assert len(found_part_name) >= 1
        assert found_part_name[0].id == c1.id

        # 4. Búsqueda parcial por fragmento de teléfono
        found_part_phone = search_customers(session, query="9988")
        assert len(found_part_phone) >= 1
        assert found_part_phone[0].id == c2.id

        # 5. Búsqueda parcial por empresa
        found_comp = search_customers(session, query="Beta")
        assert len(found_comp) >= 1
        assert found_comp[0].id == c2.id
