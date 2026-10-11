import datetime
import json
from io import BytesIO
from pathlib import Path
import shutil
import pytest
import pandas as pd

from finance_app.whatsapp_service import (
    clean_phone_number,
    detect_product_line,
    detect_closer_derivation,
    parse_whatsapp_chat_text,
    simulate_incoming_whatsapp_message,
    update_excel_with_whatsapp_leads,
    sync_whatsapp_leads,
    WhatsAppMessage,
    WhatsAppSyncState,
)


def test_clean_phone_number():
    assert clean_phone_number("+54 9 351 238-3481") == "3512 38-3481"
    assert clean_phone_number("5492615534316") == "2615 53-4316"
    assert clean_phone_number("3414 46-2806") == "3414 46-2806"


def test_detect_product_line():
    assert detect_product_line("Hola, quería consultar precio por una sonda Sentek para maíz") == "Sentek"
    assert detect_product_line("Buenas tardes, me interesa la estación meteorológica Davis") == "Davis"
    assert detect_product_line("Consulta por programador de riego y válvulas de jardín") == "Jardineria"
    assert detect_product_line("Válvula hidráulica Raphael de 3 pulgadas") == "Raphael"


def test_detect_closer_derivation():
    is_der, target = detect_closer_derivation("Pasar a Jony para cotizar")
    assert is_der == 1
    assert "Jony" in target

    is_der_l, target_l = detect_closer_derivation("Derivado a Luisa para reunión")
    assert is_der_l == 1
    assert "Luisa" in target_l

    is_der_none, target_none = detect_closer_derivation("Solo consulta general de precios")
    assert is_der_none == 0


def test_parse_whatsapp_chat_text():
    sample_chat = """
[28/01/26, 10:15:30] +54 9 351 612-9999: Hola, buenas! Quería consultar por sondas Sentek de suelo
[28/01/26, 10:16:00] Consultora: Hola! Con gusto te asesoramos. ¿Para qué cultivo?
[28/01/26, 10:17:22] +54 9 351 612-9999: Para maní y soja en Córdoba
    """
    msgs = parse_whatsapp_chat_text(sample_chat)
    assert len(msgs) >= 1
    m = msgs[0]
    assert "3516 12-9999" in m.sender_phone or "351" in m.sender_phone
    assert "Sentek" in m.text or "sondas" in m.text


def test_incremental_sync_and_deduplication(tmp_path):
    # Crear archivo de estado temporal
    state_file = tmp_path / "temp_state.json"
    state = WhatsAppSyncState(state_file)

    msg1 = simulate_incoming_whatsapp_message("Cliente Test 1", "3512 99-8877", "Consulta sonda Sentek")
    msg2 = simulate_incoming_whatsapp_message("Cliente Test 2", "2615 11-2233", "Consulta Davis estacion")

    assert not state.is_processed(msg1.message_id)
    state.mark_processed(msg1.message_id, msg1.sender_phone)
    state.save()

    # Recargar estado
    new_state = WhatsAppSyncState(state_file)
    assert new_state.is_processed(msg1.message_id)
    assert not new_state.is_processed(msg2.message_id)


def test_contact_date_compaction_preserves_alert_fields():
    from finance_app.whatsapp_service import MAX_CONTACT_DATE_COLUMNS, _compact_contact_dates

    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    raw = pd.DataFrame({"NUMERO": [1]})
    for pos, value in enumerate(dates):
        raw["FECHA CONTACTO" if pos == 0 else f"FECHA CONTACTO.{pos}"] = [value]

    compact = _compact_contact_dates(raw)
    date_cols = [c for c in compact if str(c).startswith("FECHA CONTACTO")]
    assert len(date_cols) == MAX_CONTACT_DATE_COLUMNS
    assert compact.at[0, "CANT_CONTACTOS_TOTAL"] == 40
    assert compact.at[0, "FECHA_PRIMER_CONTACTO_CRM"] == dates[0]
    assert compact.at[0, "FECHA_ULTIMO_CONTACTO_CRM"] == dates[-1]


def test_update_excel_with_whatsapp_leads(tmp_path):
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip("No se encuentra archivo de leads para pruebas")

    # Copiar a temporal para no modificar la base original durante la prueba
    temp_excel = tmp_path / "Leeds_test.xlsx"
    shutil.copy2(orig_excel, temp_excel)
    temp_state_file = tmp_path / "state_test.json"
    state = WhatsAppSyncState(temp_state_file)

    msg_new = simulate_incoming_whatsapp_message("Productor Agro Test", "3512 88-7766", "Hola, necesito cotización por estación Davis completa - Derivado Jony")
    
    # 1. Primera sincronización -> Debe insertar 1 lead nuevo
    new_cnt, upd_cnt = update_excel_with_whatsapp_leads(temp_excel, [msg_new], state)
    assert new_cnt == 1
    assert upd_cnt == 0
    assert state.is_processed(msg_new.message_id)

    # Verificar que se escribió en el Excel
    df_check = pd.read_excel(temp_excel, sheet_name="Leeds")
    assert "Productor Agro Test" in df_check["NOMBRE"].values
    assert "Davis" in df_check["PRODUCTO.1"].values

    # 2. Segunda sincronización con el mismo mensaje -> No debe duplicar porque ya fue procesado
    # Si viene un mensaje nuevo del mismo número -> Debe actualizar (nuevo toque)
    msg_followup = simulate_incoming_whatsapp_message("Productor Agro Test", "3512 88-7766", "Por favor enviar presupuesto formal por mail")
    new_cnt2, upd_cnt2 = update_excel_with_whatsapp_leads(temp_excel, [msg_followup], state)
    assert new_cnt2 == 0
    assert upd_cnt2 == 1


def test_outgoing_message_and_register_contact_event(tmp_path):
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip("No se encuentra archivo de leads para pruebas")

    temp_excel = tmp_path / "Leeds_outreach_test.xlsx"
    shutil.copy2(orig_excel, temp_excel)
    temp_state_file = tmp_path / "state_outreach.json"
    state = WhatsAppSyncState(temp_state_file)

    # 1. Probar mensaje saliente de WhatsApp (Outreach de la empresa al cliente)
    vantage_template = (
        "¡Tenemos una novedad que puede interesarte! 🌦️\n"
        "Como anteriormente nos consultaste por estaciones meteorológicas Davis, quería contarte que ya está disponible la nueva Vantage Vue..."
    )
    msg_out = WhatsAppMessage(
        message_id="msg_out_001",
        sender_phone="3512 38-3481",  # Un lead existente en la base
        sender_name="Abatech",
        timestamp=datetime.datetime.now(),
        text=vantage_template,
        is_from_me=True
    )

    new_cnt, upd_cnt = update_excel_with_whatsapp_leads(temp_excel, [msg_out], state)
    assert new_cnt == 0
    assert upd_cnt == 1

    # Verificar que se anotó como WA Saliente en el Excel
    df_check = pd.read_excel(temp_excel, sheet_name="Leeds")
    row = df_check[df_check["PRODUCTO"].astype(str).str.contains("3512 38-3481", na=False)]
    assert not row.empty
    assert "WA Saliente" in str(row["CONSULTA "].values[0])

    # 2. Probar register_lead_contact_event (Acción de 1 clic desde el Dashboard)
    from finance_app.whatsapp_service import register_lead_contact_event
    ok = register_lead_contact_event(
        excel_path=temp_excel,
        lead_id_or_phone=row["NUMERO"].values[0],
        message_text="Cotización Davis Vantage Vue enviada",
        action_type="Lanzamiento Vantage Vue"
    )
    assert ok is True

    # Verificar que se registró el nuevo toque
    df_after = pd.read_excel(temp_excel, sheet_name="Leeds")
    row_after = df_after[df_after["NUMERO"] == row["NUMERO"].values[0]]
    assert "Lanzamiento Vantage Vue" in str(row_after["CONSULTA "].values[0])


def test_get_lead_chat_timeline_bidirectional():
    from finance_app.whatsapp_service import get_lead_chat_timeline
    
    lead_row = pd.Series({
        "Contacto": "Roberto Gomez",
        "Telefono": "3512 38-3481",
        "Consulta_Detalle": "Consulta inicial | WA (28/01): Hola quiero sonda | WA Saliente (28/08): [Vantage Vue] Novedad estación",
        "Linea_Producto": "Davis"
    })

    timeline = get_lead_chat_timeline(lead_row)
    assert len(timeline) >= 3

    # Verificar presencia de mensajes salientes (Abatech) y entrantes (Cliente)
    types = [m["type"] for m in timeline]
    assert "whatsapp_out" in types
    assert "whatsapp_in" in types
    
    out_msg = next(m for m in timeline if m["type"] == "whatsapp_out")
    assert out_msg["is_lead"] is False
    assert "Abatech" in out_msg["sender"]

    in_msg = next(m for m in timeline if m["type"] == "whatsapp_in")
    assert in_msg["is_lead"] is True
    assert "Roberto" in in_msg["sender"]


def test_parse_whatsapp_export_file_txt_and_zip(tmp_path):
    from finance_app.whatsapp_service import parse_whatsapp_export_file
    import zipfile
    from io import BytesIO

    chat_txt = """[10/01/2026, 09:15:30] +54 9 351 999-1122: Hola, quería consultar cotización de Davis Vantage Vue
[10/01/2026, 09:20:00] Abatech: Hola! Te enviamos la cotización de la estación meteorológica Davis.
[12/01/2026, 14:00:00] +54 9 351 999-1122: Gracias, derivar a Jony para concretar la compra."""

    # 1. Parsear texto directo
    msgs = parse_whatsapp_export_file(chat_txt, filename="Chat de WhatsApp con +54 9 351 999-1122.txt")
    assert len(msgs) == 3
    assert msgs[0].is_from_me is False
    assert msgs[1].is_from_me is True
    assert msgs[2].is_from_me is False
    assert "3519 99-1122" in msgs[0].sender_phone or "351" in msgs[0].sender_phone

    # 2. Parsear archivo ZIP con múltiples chats
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("Chat con +54 9 341 888-2233.txt", "[15/02/2026, 11:00:00] Cliente 2: Consulta por sondas Sentek 60cm\n[15/02/2026, 11:05:00] Abatech: Hola, ficha técnica enviada.")
        z.writestr("Chat con +54 9 261 777-3344.txt", "[20/02/2026, 16:30:00] Productor Cuyo: Necesito válvulas Raphael\n[20/02/2026, 16:35:00] Abatech: Buenas tardes, te adjuntamos catálogo.")
    
    zip_bytes = zip_buffer.getvalue()
    zip_msgs = parse_whatsapp_export_file(zip_bytes, filename="chats_export.zip")
    assert len(zip_msgs) == 4
    phones = [m.sender_phone for m in zip_msgs]
    assert any("341" in p for p in phones)
    assert any("261" in p for p in phones)


def test_import_and_sync_chat_history(tmp_path):
    from finance_app.whatsapp_service import import_and_sync_chat_history, parse_whatsapp_export_file
    from tests.conftest import get_test_leads_path
    orig_excel = get_test_leads_path()
    if not orig_excel.exists():
        pytest.skip("No se encuentra archivo de leads para pruebas")

    temp_excel = tmp_path / "Leeds_history_test.xlsx"
    shutil.copy2(orig_excel, temp_excel)

    chat_content = """[05/01/2026, 10:00:00] +54 9 351 888-9999: Hola, somos una empresa agropecuaria interesada en 3 estaciones Davis Vantage
[05/01/2026, 10:15:00] Abatech: Hola! Un gusto. Disponemos de stock y entrega inmediata.
[15/01/2026, 11:00:00] +54 9 351 888-9999: ¿Me podrías cotizar además sensores de suelo Sentek?
[15/01/2026, 11:30:00] Abatech: Por supuesto, derivado a Jony para enviar propuesta formal."""

    msgs = parse_whatsapp_export_file(chat_content, filename="Chat con +54 9 351 888-9999.txt")
    res = import_and_sync_chat_history(msgs, excel_path=temp_excel)

    assert res.new_leads == 1
    assert res.processed_messages == 4

    # Verificar que el lead se guardó con múltiples fechas y toques
    from finance_app.lead_intelligence import load_and_enrich_leads
    enriched = load_and_enrich_leads(temp_excel)["Leeds"]
    row = enriched[enriched["Telefono"].astype(str).str.contains("3518", na=False)]
    assert not row.empty
    assert row["Cant_Contactos"].values[0] >= 2
    assert "WA Saliente" in str(row["Consulta_Detalle"].values[0])
    assert row["Convertido_Derivado"].values[0] == 1  # Derivado a Jony


def test_whatsapp_bridge_http_endpoints_mocked(monkeypatch):
    """
    Verifica que las funciones cliente que interactúan con el microservicio WhatsApp Bridge
    envíen las solicitudes correctas con encabezados de autenticación y manejen respuestas.
    """
    from finance_app.whatsapp_service import request_whatsapp_pairing_code, reset_whatsapp_session
    from finance_app.services.whatsapp_queue import _dispatch_to_whatsapp_bridge
    import urllib.request
    from io import BytesIO

    class MockResponse:
        def __init__(self, data: bytes, code: int = 200):
            self._data = data
            self.status = code

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    recorded_requests = []

    def mock_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if hasattr(req, "full_url"):
            recorded_requests.append(req)
        if "request-pairing-code" in url or "request-code" in url:
            return MockResponse(b'{"ok": true, "code": "ABCD-1234"}')
        elif "reset" in url:
            return MockResponse(b'{"ok": true, "message": "Session reset"}')
        elif "send-message" in url:
            return MockResponse(b'{"success": true, "messageId": "msg_999"}')
        return MockResponse(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # 1. Probar request_whatsapp_pairing_code
    code_res = request_whatsapp_pairing_code("5491122334455")
    assert isinstance(code_res, dict)
    assert code_res.get("ok") is True
    assert code_res.get("code") == "ABCD-1234"
    assert any("request" in req.full_url for req in recorded_requests)

    # 2. Probar reset_whatsapp_session
    reset_res = reset_whatsapp_session()
    assert isinstance(reset_res, dict)
    assert reset_res.get("ok") is True
    assert any("reset" in req.full_url for req in recorded_requests)

    # 3. Probar dispatch de cola de mensajes
    sent_ok, err = _dispatch_to_whatsapp_bridge("http://localhost:3001", "5491122334455", "Mensaje Test")
    assert sent_ok is True
    assert err is None
    assert any("send-message" in req.full_url for req in recorded_requests)

    for req in recorded_requests:
        assert req.get_method() == "POST"
        assert req.headers.get("Content-type") == "application/json"
        assert req.data is not None
        json.loads(req.data.decode("utf-8"))
        assert "token=" not in req.full_url.lower()

    send_request = next(req for req in recorded_requests if "send-message" in req.full_url)
    assert json.loads(send_request.data.decode("utf-8")) == {
        "phone": "5491122334455",
        "message": "Mensaje Test",
    }

    from finance_app.config import get_config
    if get_config().whatsapp_bridge_token:
        assert all(req.headers.get("Authorization", "").startswith("Bearer ") for req in recorded_requests)
