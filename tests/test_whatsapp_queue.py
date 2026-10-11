"""
Pruebas unitarias para la cola de salida de WhatsApp y política de reintentos (finance_app/services/whatsapp_queue.py).
"""

from finance_app.db.session import get_db_session, reset_db
from finance_app.db.crm_service import create_or_update_customer
from finance_app.services.whatsapp_queue import (
    enqueue_whatsapp_message,
    process_next_queue_batch,
    get_queue_metrics,
)


def test_enqueue_and_process_queue_dry_run():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        cust, _ = create_or_update_customer(session, "+5491199887766", "Mario Bros", "Sentek")

        # Encolar 2 mensajes
        msg1 = enqueue_whatsapp_message(session, cust.phone, "Hola Mario, tenemos tu cotización lista", customer_id=cust.id, priority=1)
        msg2 = enqueue_whatsapp_message(session, "+5491188776655", "Mensaje general de bienvenida", priority=5)

        assert msg1.status == "PENDING"
        assert msg2.status == "PENDING"

        metrics_before = get_queue_metrics(session)
        assert metrics_before["pending"] == 2
        assert metrics_before["sent_total"] == 0

        # Procesar en seco (dry_run)
        sent, failed = process_next_queue_batch(session, batch_size=10, dry_run=True)
        assert sent == 2
        assert failed == 0

        metrics_after = get_queue_metrics(session)
        assert metrics_after["pending"] == 0
        assert metrics_after["sent_total"] == 2
