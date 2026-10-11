"""
Pruebas automatizadas para el módulo de IA Local (ai_service).
Cubre detección de disponibilidad, análisis de mensajes estructurados,
fallbacks ante fallos de conexión y síntesis de historial conversacional.
"""

import pytest
from unittest.mock import patch, MagicMock

from finance_app.services.ai_service import (
    LeadMessageAnalysis,
    get_ai_status,
    is_ai_available,
    analyze_whatsapp_message,
    analyze_conversation_history,
    ask_crm_assistant,
    _heuristic_fallback_analysis,
)


def test_ai_status_structure():
    """Verifica que el estado del servicio retorne todas las claves esperadas."""
    status = get_ai_status(force_refresh=True)
    assert isinstance(status, dict)
    assert "enabled" in status
    assert "available" in status
    assert "models" in status
    assert "current_model" in status


def test_heuristic_fallback_analysis():
    """Valida que el fallback heurístico genere una estructura válida sin degradar el sistema."""
    text = "Hola, necesito urgente precio de sonda Sentek Drill Drop para maíz. Jony avisame."
    result = _heuristic_fallback_analysis(text, sender_name="Carlos Gomez", sender_phone="+5491122334455")
    
    assert isinstance(result, LeadMessageAnalysis)
    assert result.product_line == "Sentek"
    assert result.temperature == "HOT"
    assert result.urgency == "ALTA"
    assert result.suggested_closer == "Jony"
    assert result.is_ai_generated is False
    assert result.client_name == "Carlos Gomez"


def test_analyze_whatsapp_message_empty():
    """Valida el manejo seguro de mensajes vacíos o nulos."""
    result = analyze_whatsapp_message("", sender_name="Anonimo")
    assert isinstance(result, LeadMessageAnalysis)
    assert result.product_line in ("General", "Sentek")


def test_analyze_whatsapp_message_mocked_llm():
    """Prueba la deserialización correcta cuando la API LLM responde un JSON válido."""
    mock_response = {
        "nombre": "Lucas Rossi",
        "localidad": "Venado Tuerto",
        "provincia": "Santa Fe",
        "producto_interes": "Davis",
        "intencion": "Presupuesto",
        "temperatura": "HOT",
        "urgencia": "ALTA",
        "objeciones": "Consulta plazos de entrega",
        "resumen_ejecutivo": "Interesado en estación meteorológica Davis.",
        "accion_recomendada": "Enviar cotización formal con flete.",
        "closer_sugerido": "Luisa",
    }
    
    with patch("finance_app.services.ai_service._call_llm", return_value=mock_response):
        res = analyze_whatsapp_message("Hola, soy Lucas de Venado Tuerto. Quiero comprar una Davis.", sender_name="Lucas")
        assert res.client_name == "Lucas Rossi"
        assert res.locality == "Venado Tuerto"
        assert res.province == "Santa Fe"
        assert res.product_line == "Davis"
        assert res.temperature == "HOT"
        assert res.urgency == "ALTA"
        assert res.suggested_closer == "Luisa"
        assert res.is_ai_generated is True


def test_analyze_whatsapp_message_fallback_on_network_error():
    """Prueba la resiliencia: si la llamada a la API LLM devuelve None o falla, se ejecuta el fallback."""
    with patch("finance_app.services.ai_service._call_llm", return_value=None):
        res = analyze_whatsapp_message("Quiero saber sobre la valvula Raphael hidraulica", sender_name="Mario")
        assert isinstance(res, LeadMessageAnalysis)
        assert res.product_line == "Raphael"
        assert res.is_ai_generated is False


def test_analyze_conversation_history_empty():
    """Verifica la respuesta segura ante historiales vacíos."""
    res = analyze_conversation_history([])
    assert isinstance(res, dict)
    assert "summary" in res
    assert res["temperature"] == "COLD"


def test_ask_crm_assistant_offline():
    """Verifica que el copiloto informe amigablemente si la IA no está disponible."""
    with patch("finance_app.services.ai_service.is_ai_available", return_value=False):
        res = ask_crm_assistant("¿Cuáles son los leads más calientes?", {})
        assert "no se encuentra disponible" in res


def test_whatsapp_message_missing_location_warning():
    """Valida la detección explícita cuando el cliente no informa lugar de procedencia."""
    mock_response = {
        "nombre": "Agropecuaria El Roble",
        "localidad": None,
        "provincia": None,
        "producto_interes": "Sentek",
        "que_esta_pidiendo": "Cotización de 2 sondas de 90cm",
        "intencion": "Presupuesto",
        "temperatura": "HOT",
        "urgencia": "ALTA",
        "closer_sugerido": "Jony",
        "accion_recomendada": "Consultar zona o campo para coordinar flete",
        "datos_faltantes": ["⚠️ Este cliente no informó lugar / localidad de procedencia"],
    }
    with patch("finance_app.services.ai_service._call_llm", return_value=mock_response):
        res = analyze_whatsapp_message("Buenas, pasame precio por dos sondas Sentek de 90cm", sender_name="El Roble")
        assert res.product_line == "Sentek"
        assert res.suggested_closer == "Jony"
        assert res.locality is None
        assert any("no informó lugar" in alert.lower() for alert in res.missing_info)
        assert "no informó lugar" in res.derivation_summary.lower()


def test_process_document_with_ai_and_math_validation():
    """Valida el procesamiento y auditoría contable estricta de documentos (llm/06-factura.mjs)."""
    from finance_app.services.ai_service import process_document_with_ai

    # 1. Documento con cálculos exactos
    mock_valid_doc = {
        "tipo_documento": "Factura A",
        "numero": "0001-00004589",
        "fecha": "2026-10-02",
        "emisor": {"nombre": "Abatech SRL", "cuit": "30-71123456-9"},
        "cliente": {
            "nombre": "Estancia Las Lilas SA",
            "cuit": "30-55667788-2",
            "telefono": "+54 9 351 555-1234",
            "localidad": "Río Cuarto",
            "provincia": "Córdoba",
        },
        "items": [
            {"descripcion": "Sonda Sentek Drill & Drop 90cm", "cantidad": 2.0, "precio_unitario": 1500.0, "subtotal": 3000.0},
            {"descripcion": "Módem Telemetría 4G", "cantidad": 1.0, "precio_unitario": 500.0, "subtotal": 500.0},
        ],
        "neto": 3500.0,
        "iva": 735.0,
        "total": 4235.0,
        "moneda": "USD",
        "linea_producto": "Sentek",
        "resumen_ejecutivo": "Facturación de sondas Sentek y telemetría para Estancia Las Lilas.",
    }

    with patch("finance_app.services.ai_service._call_llm", return_value=mock_valid_doc):
        res = process_document_with_ai(b"dummy_content", "factura_valida.pdf")
        assert res["cuentas_cierran"] is True
        assert len(res["advertencias"]) == 0
        assert res["primera_devolucion"]["total"] == 4235.0
        assert "Las cuentas cierran" in res["primera_devolucion"]["mensaje_control"]

    # 2. Documento con inconsistencias numéricas
    mock_invalid_doc = dict(mock_valid_doc)
    mock_invalid_doc["total"] = 9999.0  # El total no coincide con neto + iva

    with patch("finance_app.services.ai_service._call_llm", return_value=mock_invalid_doc):
        res_err = process_document_with_ai(b"dummy_content", "factura_error.pdf")
        assert res_err["cuentas_cierran"] is False
        assert any("no coincide con el total" in adv.lower() for adv in res_err["advertencias"])


def test_save_document_to_database_integration():
    """Valida la incorporación del documento aceptado al CRM (Customer, Opportunity, ActivityLog)."""
    from finance_app.services.ai_service import save_document_to_database
    from finance_app.db.session import get_db_session, init_db
    from finance_app.db.models import Customer, Opportunity

    init_db()

    doc_data = {
        "filename": "remito_prueba.pdf",
        "datos": {
            "tipo_documento": "Remito Comercial",
            "numero": "R-0002-1234",
            "fecha": "2026-10-02",
            "linea_producto": "Davis",
            "total": 1200000.0,
            "resumen_ejecutivo": "Entrega de estación meteorológica Davis Vantage Pro 2.",
            "cliente": {
                "nombre": "Agropecuaria Santa Maria",
                "cuit": "30-99887766-1",
                "telefono": "+54 9 353 444-9988",
                "localidad": "Villa María",
                "provincia": "Córdoba",
            },
            "items": [
                {"descripcion": "Estación Davis Vantage Pro 2", "cantidad": 1.0, "precio_unitario": 1200000.0, "subtotal": 1200000.0}
            ],
        },
        "advertencias": [],
        "cuentas_cierran": True,
    }

    result = save_document_to_database(doc_data)
    assert result["success"] is True
    assert result["customer_id"] > 0
    assert result["opportunity_id"] > 0
    assert result["total_amount"] == 1200000.0

    # Verificar en la base de datos
    with get_db_session() as session:
        customer = session.query(Customer).filter_by(id=result["customer_id"]).first()
        assert customer is not None
        assert customer.full_name == "Agropecuaria Santa Maria"
        assert customer.locality == "Villa María"
        assert customer.product_line == "Davis"

        opp = session.query(Opportunity).filter_by(id=result["opportunity_id"]).first()
        assert opp is not None
        assert opp.customer_id == customer.id
        assert opp.amount_ars == 1200000.0
