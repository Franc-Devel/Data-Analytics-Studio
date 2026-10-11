import datetime
from pathlib import Path
import shutil
import pandas as pd
import pytest

from finance_app.lead_intelligence import (
    load_and_enrich_leads,
    compute_lead_kpis,
    generate_reactivation_message,
    get_daily_reactivation_batch,
    calculate_lead_score,
    build_whatsapp_link,
)
from finance_app.whatsapp_service import (
    register_lead_contact_event,
    update_excel_with_whatsapp_leads,
    WhatsAppMessage,
    WhatsAppSyncState,
)


def test_reactivation_message_generation_and_spintax():
    lead_sample = pd.Series({
        'ID_Lead': 101,
        'Contacto': 'Esteban Ramos',
        'Telefono': '351 555-4321',
        'Linea_Producto': 'Davis',
        'Localidad': 'Rio Cuarto',
        'Provincia': 'Cordoba',
        'Lead_Score': 45,
        'Dias_Sin_Contacto': 45,
    })

    msg_short = generate_reactivation_message(lead_sample, strategy='short', variant_seed=1)
    msg_news = generate_reactivation_message(lead_sample, strategy='news', variant_seed=1)
    msg_budget = generate_reactivation_message(lead_sample, strategy='budget', variant_seed=1)
    msg_discard = generate_reactivation_message(lead_sample, strategy='discard', variant_seed=1)

    assert 'Esteban' in msg_short or 'Hola' in msg_short
    assert 'davis' in msg_short.lower() or 'estaci' in msg_short.lower() or 'clima' in msg_short.lower()
    assert len(msg_short.split()) < 25

    assert 'Abatech' in msg_news
    assert 'Davis' in msg_news or 'davis' in msg_news

    assert any(k in msg_budget.lower() for k in ['financ', 'cotiz', 'presupuesto'])
    assert any(k in msg_discard.lower() for k in ['pausemos', 'campana', 'campaña', 'consulta'])

    msg_v1 = generate_reactivation_message(lead_sample, strategy='news', variant_seed=10)
    msg_v2 = generate_reactivation_message(lead_sample, strategy='news', variant_seed=99)
    assert isinstance(msg_v1, str) and isinstance(msg_v2, str)
    assert len(msg_v1) > 20 and len(msg_v2) > 20


def test_daily_reactivation_batch_selection():
    df_test = pd.DataFrame([
        {'ID_Lead': 1, 'Contacto': 'Juan', 'Telefono': '351 111-2222', 'Linea_Producto': 'Sentek', 'Lead_Score': 70, 'Dias_Sin_Contacto': 30, 'Convertido_Derivado': 0, 'Estado_Lead': 'Cold'},
        {'ID_Lead': 2, 'Contacto': 'Pedro', 'Telefono': '351 222-3333', 'Linea_Producto': 'Davis', 'Lead_Score': 85, 'Dias_Sin_Contacto': 60, 'Convertido_Derivado': 0, 'Estado_Lead': 'Cold'},
        {'ID_Lead': 3, 'Contacto': 'Lucas', 'Telefono': '351 333-4444', 'Linea_Producto': 'Jardineria', 'Lead_Score': 50, 'Dias_Sin_Contacto': 0, 'Convertido_Derivado': 0, 'Estado_Lead': 'Warm'},
        {'ID_Lead': 4, 'Contacto': 'Marcos', 'Telefono': '351 444-5555', 'Linea_Producto': 'Sentek', 'Lead_Score': 90, 'Dias_Sin_Contacto': 20, 'Convertido_Derivado': 1, 'Estado_Lead': 'Ganado'},
        {'ID_Lead': 5, 'Contacto': 'Sin Tel', 'Telefono': '', 'Linea_Producto': 'Sentek', 'Lead_Score': 40, 'Dias_Sin_Contacto': 40, 'Convertido_Derivado': 0, 'Estado_Lead': 'Cold'},
    ])

    batch = get_daily_reactivation_batch(df_test, batch_size=2)
    assert len(batch) == 2
    assert batch.iloc[0]['ID_Lead'] == 2
    assert batch.iloc[1]['ID_Lead'] == 1
    assert 3 not in batch['ID_Lead'].values
    assert 4 not in batch['ID_Lead'].values
    assert 5 not in batch['ID_Lead'].values


def test_full_resurrection_lifecycle(tmp_path):
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip('No se encuentra archivo de leads para pruebas')

    temp_excel = tmp_path / 'Leeds_resurrection_test.xlsx'
    shutil.copy2(orig_excel, temp_excel)
    temp_state = WhatsAppSyncState(tmp_path / 'state_resurrect.json')

    sheets_1 = load_and_enrich_leads(temp_excel)
    master_1 = sheets_1['Leeds']
    cold_leads = master_1[
        (master_1['Dias_Sin_Contacto'] >= 14) &
        (master_1['Convertido_Derivado'] == 0) &
        (master_1['Telefono'].astype(str).str.len() >= 6)
    ]
    target_lead = cold_leads.iloc[0]
    lead_id = target_lead['ID_Lead']
    lead_phone = target_lead['Telefono']

    msg_react = generate_reactivation_message(target_lead, strategy='news', variant_seed=42)
    success = register_lead_contact_event(
        excel_path=temp_excel,
        lead_id_or_phone=lead_id,
        message_text=msg_react,
        action_type='Reactivacion - Novedad'
    )
    assert success is True

    reply_msg = WhatsAppMessage(
        message_id='msg_react_reply_001',
        sender_phone=lead_phone,
        sender_name=target_lead['Contacto'],
        timestamp=datetime.datetime.now(),
        text='Hola! Si, me interesa ver el reporte tecnico y presupuesto actualizado.',
        is_from_me=False
    )
    new_c, upd_c = update_excel_with_whatsapp_leads(temp_excel, [reply_msg], temp_state)
    assert upd_c == 1

    sheets_2 = load_and_enrich_leads(temp_excel)
    master_2 = sheets_2['Leeds']
    updated_lead = master_2[master_2['ID_Lead'] == lead_id].iloc[0]

    assert updated_lead['Is_Reactivado'] == 1
    assert updated_lead['Lead_Score'] > target_lead['Lead_Score']
    assert updated_lead['Dias_Sin_Contacto'] == 0
    assert 'Hoy' in updated_lead['Recontacto_Prioridad']

    kpis = compute_lead_kpis(master_2)
    assert kpis.leads_reactivados >= 1
