"""
Nexo Analytics - Servicio de Cola de Mensajería Saliente y Reintentos para WhatsApp
Garantiza entregabilidad, cadencia controlada y política de reintentos exponencial.
"""

from __future__ import annotations
import datetime
from typing import Optional, Dict, Tuple, List
import urllib.request
import json

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from finance_app.db.models import WhatsAppQueueMessage, Customer
from finance_app.db.crm_service import log_customer_activity
from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("whatsapp_queue")


def enqueue_whatsapp_message(
    session: Session,
    phone: str,
    message_text: str,
    customer_id: Optional[int] = None,
    media_path: Optional[str] = None,
    priority: int = 5,
    max_attempts: int = 3,
) -> WhatsAppQueueMessage:
    """Encola un mensaje saliente de WhatsApp para despacho en segundo plano."""
    clean_phone = phone.strip()
    
    # Si no se pasó customer_id, buscar por teléfono
    if customer_id is None:
        cust = session.query(Customer).filter(Customer.phone == clean_phone).first()
        if cust:
            customer_id = cust.id

    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    queue_item = WhatsAppQueueMessage(
        customer_id=customer_id,
        phone=clean_phone,
        message_text=message_text.strip(),
        media_path=media_path,
        priority=priority,
        status="PENDING",
        attempts=0,
        max_attempts=max_attempts,
        next_retry_at=now_utc,
        created_at=now_utc,
    )
    session.add(queue_item)
    session.flush()
    logger.info(f"Mensaje encolado (ID: {queue_item.id}) para {clean_phone} (Prioridad: {priority})")
    return queue_item


def process_next_queue_batch(
    session: Session,
    batch_size: int = 5,
    dry_run: bool = False,
) -> Tuple[int, int]:
    """
    Procesa un lote de mensajes pendientes cuyo tiempo de reintento haya llegado.
    Retorna (enviados_ok, fallidos).
    """
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    pending_items = (
        session.query(WhatsAppQueueMessage)
        .filter(
            and_(
                WhatsAppQueueMessage.status.in_(["PENDING", "FAILED_RETRYING"]),
                WhatsAppQueueMessage.next_retry_at <= now,
                WhatsAppQueueMessage.attempts < WhatsAppQueueMessage.max_attempts,
            )
        )
        .order_by(WhatsAppQueueMessage.priority.asc(), WhatsAppQueueMessage.created_at.asc())
        .limit(batch_size)
        .all()
    )

    if not pending_items:
        return 0, 0

    sent_count = 0
    failed_count = 0
    cfg = get_config()

    for item in pending_items:
        item.attempts += 1
        item.status = "PROCESSING"
        session.flush()

        if dry_run:
            # Modo simulación
            item.status = "SENT"
            item.sent_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            sent_count += 1
            if item.customer_id:
                log_customer_activity(
                    session=session,
                    customer_id=item.customer_id,
                    summary="Mensaje WhatsApp enviado (Simulación / Cola)",
                    channel="WHATSAPP",
                    direction="OUTBOUND",
                    content=item.message_text,
                )
            continue

        # Envío real a través del bridge HTTP
        success, error_msg = _dispatch_to_whatsapp_bridge(cfg.whatsapp_bridge_url, item.phone, item.message_text)

        if success:
            item.status = "SENT"
            item.sent_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            item.last_error = None
            sent_count += 1
            logger.info(f"Mensaje ID {item.id} enviado exitosamente a {item.phone}")
            
            if item.customer_id:
                log_customer_activity(
                    session=session,
                    customer_id=item.customer_id,
                    summary="Mensaje WhatsApp saliente entregado vía Cola",
                    channel="WHATSAPP",
                    direction="OUTBOUND",
                    content=item.message_text,
                )
        else:
            item.last_error = error_msg
            if item.attempts >= item.max_attempts:
                item.status = "FAILED"
                logger.error(f"Mensaje ID {item.id} a {item.phone} falló definitivamente tras {item.attempts} intentos: {error_msg}")
            else:
                # Backoff exponencial: 1 min, 4 min, 9 min...
                backoff_seconds = (item.attempts ** 2) * 60
                item.next_retry_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(seconds=backoff_seconds)
                item.status = "FAILED_RETRYING"
                logger.warning(f"Mensaje ID {item.id} falló (intento {item.attempts}/{item.max_attempts}). Próximo reintento en {backoff_seconds}s: {error_msg}")
            failed_count += 1

    session.flush()
    return sent_count, failed_count


def _dispatch_to_whatsapp_bridge(bridge_url: str, phone: str, text: str) -> Tuple[bool, Optional[str]]:
    """Envía la solicitud POST al microservicio Node.js / Baileys con autenticación por token."""
    cfg = get_config()
    endpoint = f"{bridge_url.rstrip('/')}/send-message"
    payload = json.dumps({"phone": phone, "message": text}).encode("utf-8")
    
    headers = {"Content-Type": "application/json"}
    if cfg.whatsapp_bridge_token:
        headers["Authorization"] = f"Bearer {cfg.whatsapp_bridge_token}"

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status in (200, 201):
                return True, None
            return False, f"HTTP Status: {response.status}"
    except Exception as e:
        return False, str(e)



def get_queue_metrics(session: Session) -> Dict[str, int]:
    """Obtiene el resumen de estado de la cola de WhatsApp."""
    return {
        "pending": session.query(WhatsAppQueueMessage).filter(WhatsAppQueueMessage.status.in_(["PENDING", "FAILED_RETRYING"])).count(),
        "sent_total": session.query(WhatsAppQueueMessage).filter(WhatsAppQueueMessage.status == "SENT").count(),
        "failed_total": session.query(WhatsAppQueueMessage).filter(WhatsAppQueueMessage.status == "FAILED").count(),
        "total": session.query(WhatsAppQueueMessage).count(),
    }
