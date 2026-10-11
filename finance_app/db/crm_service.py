"""
Nexo Analytics - Servicio Central de CRM, Ficha 360°, Oportunidades y Tareas
Gestiona operaciones relacionales, control de acceso estricto (RBAC / Anti-IDOR) y cumplimiento de privacidad (Ley 25.326).
"""

from __future__ import annotations
import datetime
import hashlib
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
from sqlalchemy import or_, func, desc
from sqlalchemy.orm import Session

from finance_app.db.models import Customer, CustomerSearchToken, Opportunity, Task, ActivityLog, User, PendingCRMProposal, utc_now
from finance_app.db.audit_service import log_audit_event
from finance_app.db.crypto import compute_blind_index, compute_name_token_hashes, compute_phone_token_hashes
from finance_app.logging_config import get_logger

logger = get_logger("crm_service")


def _sync_customer_search_tokens(session: Session, customer: Customer) -> None:
    """Regenera atómicamente los tokens normalizados de un cliente."""
    session.flush()
    session.query(CustomerSearchToken).filter(
        CustomerSearchToken.customer_id == customer.id
    ).delete(synchronize_session=False)
    name_tokens = compute_name_token_hashes(customer.full_name, customer.company)
    phone_tokens = compute_phone_token_hashes(customer.phone)
    session.add_all([
        CustomerSearchToken(customer_id=customer.id, token_type=token_type, token_hash=token_hash)
        for token_type, tokens in (("name", name_tokens), ("phone", phone_tokens))
        for token_hash in tokens
    ])


def _extract_user_context(
    user_actor: Optional[User | Dict[str, Any] | str],
    session: Optional[Session] = None,
) -> Tuple[Optional[int], str, str]:
    """Extrae (user_id, username, role) a partir del actor proporcionado."""
    if user_actor is None:
        return None, "system", "admin"

    if isinstance(user_actor, User):
        return user_actor.id, user_actor.username, user_actor.role

    if isinstance(user_actor, dict):
        return (
            user_actor.get("id"),
            user_actor.get("username", "anonymous"),
            user_actor.get("role", "closer"),
        )

    if isinstance(user_actor, str):
        if session:
            db_user = session.query(User).filter(User.username == user_actor).first()
            if db_user:
                return db_user.id, db_user.username, db_user.role
        return None, user_actor, "admin" if user_actor in ("system", "admin") else "closer"

    return None, "anonymous", "closer"


def _check_closer_access(customer: Customer, user_actor: Optional[User | Dict[str, Any] | str], session: Optional[Session] = None) -> None:
    """Valida que un closer solo acceda a sus clientes asignados (Prevención IDOR)."""
    user_id, username, role = _extract_user_context(user_actor, session)
    if role == "closer" and user_id is not None:
        if customer.assigned_user_id is not None and customer.assigned_user_id != user_id:
            logger.warning(f"Intento de acceso IDOR no autorizado: Closer '{username}' (ID {user_id}) sobre cliente ID {customer.id}")
            raise PermissionError(f"Acceso denegado: El cliente no se encuentra asignado a su usuario.")


# =========================================================================
# 1. GESTIÓN DE CLIENTES & FICHA ÚNICA 360°
# =========================================================================

def create_or_update_customer(
    session: Session,
    phone: str,
    full_name: str,
    product_line: Optional[str] = None,
    province: Optional[str] = None,
    locality: Optional[str] = None,
    region: Optional[str] = None,
    lead_score: int = 50,
    segment: str = "WARM",
    status: str = "NUEVO",
    assigned_user_id: Optional[int] = None,
    remote_id: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    notes: Optional[str] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Tuple[Customer, bool]:
    """
    Crea un nuevo cliente o actualiza uno existente por número telefónico normalizado.
    Valida autorización a nivel de servicio.
    """
    _, username, role = _extract_user_context(user_actor, session)
    if role == "viewer":
        raise PermissionError("Los usuarios con rol 'viewer' no tienen permisos de escritura.")

    clean_phone = phone.strip()
    blind_phone = compute_blind_index(clean_phone, is_phone=True)
    blind_name = compute_blind_index(full_name, is_phone=False)
    
    customer = session.query(Customer).filter(Customer.phone_blind_index == blind_phone).first()
    created = False
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    if customer is None:
        created = True
        customer = Customer(
            phone=clean_phone,
            phone_blind_index=blind_phone,
            full_name=full_name.strip(),
            name_blind_index=blind_name,
            remote_id=remote_id,
            email=email,
            company=company,
            product_line=product_line,
            province=province,
            locality=locality,
            region=region,
            lead_score=lead_score,
            segment=segment,
            status=status,
            assigned_user_id=assigned_user_id,
            first_contact_at=now,
            last_contact_at=now,
            total_contacts=1,
            notes=notes,
        )
        session.add(customer)
        session.flush()
        _sync_customer_search_tokens(session, customer)
        log_audit_event(session, "CREATE", "Customer", customer.id, user=username, new_data={"phone": clean_phone, "name": full_name})
    else:
        # Validación de propiedad para closers en actualización
        _check_closer_access(customer, user_actor, session)

        old_data = {"name": customer.full_name, "status": customer.status, "score": customer.lead_score}
        if full_name:
            customer.full_name = full_name.strip()
            customer.name_blind_index = blind_name
        if product_line:
            customer.product_line = product_line
        if province:
            customer.province = province
        if locality:
            customer.locality = locality
        if region:
            customer.region = region
        if lead_score is not None:
            customer.lead_score = lead_score
        if segment:
            customer.segment = segment
        if status:
            customer.status = status
        if assigned_user_id is not None and role in ("admin", "manager"):
            customer.assigned_user_id = assigned_user_id
        if email:
            customer.email = email
        if company:
            customer.company = company
        if notes:
            customer.notes = notes
        if not customer.phone_blind_index:
            customer.phone_blind_index = blind_phone
            
        customer.last_contact_at = now
        customer.total_contacts += 1
        _sync_customer_search_tokens(session, customer)
        session.flush()
        log_audit_event(session, "UPDATE", "Customer", customer.id, user=username, old_data=old_data, new_data={"status": customer.status, "score": customer.lead_score})

    return customer, created


def get_customer_by_id(
    session: Session,
    customer_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Optional[Customer]:
    """Obtiene un cliente por su ID de base de datos con verificación anti-IDOR."""
    customer = session.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return None
    if user_actor is not None:
        _check_closer_access(customer, user_actor, session)
    return customer


def get_customer_by_phone(
    session: Session,
    phone: str,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Optional[Customer]:
    """Obtiene un cliente por su número de teléfono con verificación de acceso y Blind Index."""
    clean_phone = phone.strip()
    blind_idx = compute_blind_index(clean_phone, is_phone=True)
    customer = session.query(Customer).filter(Customer.phone_blind_index == blind_idx).first()
    if not customer:
        return None
    if user_actor is not None:
        _check_closer_access(customer, user_actor, session)
    return customer


def search_customers(
    session: Session,
    query: Optional[str] = None,
    product_line: Optional[str] = None,
    province: Optional[str] = None,
    status: Optional[str] = None,
    segment: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    limit: int = 50,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> List[Customer]:
    """Busca clientes con filtros dinámicos y aislamiento automático para closers."""
    user_id, _, role = _extract_user_context(user_actor, session)
    
    q = session.query(Customer)
    
    # Aislamiento por Tenancy: Si es closer, solo ve sus clientes asignados
    if role == "closer" and user_id is not None:
        q = q.filter(Customer.assigned_user_id == user_id)
    elif assigned_user_id is not None:
        q = q.filter(Customer.assigned_user_id == assigned_user_id)

    if not query:
        return q.order_by(desc(Customer.lead_score), desc(Customer.last_contact_at)).limit(limit).all()

    clean_q = query.strip()
    blind_phone = compute_blind_index(clean_q, is_phone=True)
    blind_name = compute_blind_index(clean_q, is_phone=False)

    # 1. Búsqueda en SQL: Blind Index exacto, tokens ciegos de palabras y campos no confidenciales
    search_conditions = [
        Customer.locality.ilike(f"%{clean_q}%"),
        Customer.province.ilike(f"%{clean_q}%"),
    ]
    if blind_phone:
        search_conditions.append(Customer.phone_blind_index == blind_phone)
    if blind_name:
        search_conditions.append(Customer.name_blind_index == blind_name)

    # Tokenizar términos de búsqueda para matching de palabras y teléfonos en SQL en 100% de registros
    import re
    query_words = re.findall(r"\w+", clean_q.lower())
    for w in query_words:
        if len(w) >= 2:
            tok = compute_blind_index(w, is_phone=False)
            if tok:
                search_conditions.append(Customer.search_tokens.any(
                    (CustomerSearchToken.token_type == "name") &
                    (CustomerSearchToken.token_hash == tok)
                ))

    clean_digits = re.sub(r"\D", "", clean_q)
    if len(clean_digits) >= 4:
        tok_digit = compute_blind_index(clean_digits, is_phone=True)
        if tok_digit:
            search_conditions.append(Customer.search_tokens.any(
                (CustomerSearchToken.token_type == "phone") &
                (CustomerSearchToken.token_hash == tok_digit)
            ))

    sql_matches = q.filter(or_(*search_conditions)).order_by(desc(Customer.lead_score), desc(Customer.last_contact_at)).limit(limit).all()
    return sql_matches


# =========================================================================
# 2. PIPELINE & OPORTUNIDADES COMERCIALES
# =========================================================================

def create_opportunity(
    session: Session,
    customer_id: int,
    title: str,
    product: str,
    amount_ars: float = 0.0,
    stage: str = "PROSPECCION",
    probability_pct: int = 20,
    expected_close_date: Optional[datetime.date] = None,
    assigned_closer_id: Optional[int] = None,
    notes: Optional[str] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Opportunity:
    """Crea una nueva oportunidad comercial con validación de autorización."""
    user_id, username, role = _extract_user_context(user_actor, session)
    if role == "viewer":
        raise PermissionError("Los usuarios con rol 'viewer' no pueden crear oportunidades.")

    # Si es closer, la oportunidad se le asigna a sí mismo
    effective_closer_id = user_id if (role == "closer" and user_id) else assigned_closer_id

    opp = Opportunity(
        customer_id=customer_id,
        title=title.strip(),
        product=product.strip(),
        amount_ars=amount_ars,
        stage=stage,
        probability_pct=probability_pct,
        expected_close_date=expected_close_date,
        assigned_closer_id=effective_closer_id,
        notes=notes,
    )
    session.add(opp)
    session.flush()
    log_audit_event(session, "CREATE", "Opportunity", opp.id, user=username, new_data={"title": title, "amount": amount_ars, "stage": stage})
    return opp


def update_opportunity_stage(
    session: Session,
    opportunity_id: int,
    new_stage: str,
    probability_pct: Optional[int] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Optional[Opportunity]:
    """Actualiza la etapa de una oportunidad en el pipeline con control de acceso."""
    user_id, username, role = _extract_user_context(user_actor, session)
    if role == "viewer":
        raise PermissionError("Los usuarios con rol 'viewer' no pueden modificar oportunidades.")

    opp = session.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return None

    if role == "closer" and user_id is not None and opp.assigned_closer_id != user_id:
        raise PermissionError("No puede modificar una oportunidad asignada a otro closer.")

    old_stage = opp.stage
    opp.stage = new_stage
    if probability_pct is not None:
        opp.probability_pct = probability_pct
    else:
        stage_probs = {
            "PROSPECCION": 10,
            "CONTACTADO": 25,
            "REUNION_AGENDADA": 50,
            "PROPUESTA_ENVIADA": 70,
            "NEGOCIACION": 85,
            "CERRADO_GANADO": 100,
            "CERRADO_PERDIDO": 0,
        }
        opp.probability_pct = stage_probs.get(new_stage, opp.probability_pct)

    session.flush()
    log_audit_event(session, "UPDATE_STAGE", "Opportunity", opp.id, user=username, old_data={"stage": old_stage}, new_data={"stage": new_stage, "prob": opp.probability_pct})
    return opp


def get_opportunities_by_closer(
    session: Session,
    closer_id: Optional[int] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> List[Opportunity]:
    """Obtiene oportunidades con filtrado estricto por closer según rol."""
    user_id, _, role = _extract_user_context(user_actor, session)
    q = session.query(Opportunity)
    
    if role == "closer" and user_id is not None:
        q = q.filter(Opportunity.assigned_closer_id == user_id)
    elif closer_id is not None:
        q = q.filter(Opportunity.assigned_closer_id == closer_id)

    return q.order_by(desc(Opportunity.created_at)).all()


# =========================================================================
# 3. GESTIÓN DE TAREAS & ALERTAS DE SEGUIMIENTO
# =========================================================================

def create_task(
    session: Session,
    customer_id: int,
    title: str,
    due_date: datetime.datetime,
    task_type: str = "WHATSAPP",
    priority: str = "MEDIA",
    assigned_user_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Task:
    """Crea una nueva tarea de seguimiento con validación de rol."""
    user_id, username, role = _extract_user_context(user_actor, session)
    if role == "viewer":
        raise PermissionError("Los usuarios con rol 'viewer' no pueden crear tareas.")

    effective_user_id = user_id if (role == "closer" and user_id) else assigned_user_id

    task = Task(
        customer_id=customer_id,
        title=title.strip(),
        due_date=due_date,
        task_type=task_type.upper(),
        priority=priority.upper(),
        status="PENDIENTE",
        assigned_user_id=effective_user_id,
        opportunity_id=opportunity_id,
    )
    session.add(task)
    session.flush()
    log_audit_event(session, "CREATE", "Task", task.id, user=username, new_data={"title": title, "due": str(due_date)})
    return task


def complete_task(
    session: Session,
    task_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Optional[Task]:
    """Marca una tarea como completada."""
    user_id, username, role = _extract_user_context(user_actor, session)
    if role == "viewer":
        raise PermissionError("Los usuarios con rol 'viewer' no pueden modificar tareas.")

    task = session.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    if role == "closer" and user_id is not None and task.assigned_user_id != user_id:
        raise PermissionError("No puede completar una tarea asignada a otro usuario.")

    task.status = "COMPLETADA"
    task.completed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    session.flush()
    log_audit_event(session, "COMPLETE", "Task", task.id, user=username)
    return task


def get_pending_tasks(
    session: Session,
    user_id: Optional[int] = None,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> List[Task]:
    """Obtiene tareas pendientes con aislamiento para closers."""
    actor_id, _, role = _extract_user_context(user_actor, session)
    q = session.query(Task).filter(Task.status == "PENDIENTE")
    
    if role == "closer" and actor_id is not None:
        q = q.filter(Task.assigned_user_id == actor_id)
    elif user_id is not None:
        q = q.filter(Task.assigned_user_id == user_id)

    return q.order_by(Task.due_date.asc()).all()


# =========================================================================
# 4. HISTORIAL DE ACTIVIDAD MULTICANAL (360°)
# =========================================================================

def log_customer_activity(
    session: Session,
    customer_id: int,
    summary: str,
    channel: str = "WHATSAPP",
    direction: str = "OUTBOUND",
    content: Optional[str] = None,
    user_id: Optional[int] = None,
    metadata_json: Optional[str] = None,
) -> ActivityLog:
    """Registra una interacción o evento en el historial del cliente."""
    activity = ActivityLog(
        customer_id=customer_id,
        user_id=user_id,
        channel=channel.upper(),
        direction=direction.upper(),
        summary=summary.strip(),
        content=content,
        metadata_json=metadata_json,
        created_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    )
    session.add(activity)
    session.flush()
    return activity


# =========================================================================
# 5. PRIVACIDAD & CUMPLIMIENTO LEY ARGENTINA 25.326 (SAR & DERECHO AL OLVIDO)
# =========================================================================

def anonymize_customer(
    session: Session,
    customer_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> bool:
    """
    Aplica el 'Derecho al Olvido' (Supresión de datos personales) conforme a la Ley 25.326.
    Anonimiza toda la PII reemplazándola por identificadores seudonimizados no reversibles,
    conservando las métricas agregadas comerciales para consistencia contable.
    """
    _, username, role = _extract_user_context(user_actor, session)
    if role not in ("admin", "manager"):
        raise PermissionError("Solo administradores y gerentes pueden ejecutar anonimización de datos personales.")

    customer = session.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return False

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    anon_tag = hashlib.sha256(f"ANON_{customer.id}_{now_iso}".encode()).hexdigest()[:8].upper()

    old_phone = customer.phone
    customer.full_name = f"Titular Suprimido #{anon_tag}"
    customer.phone = f"+000000{anon_tag}"
    customer.email = f"anonymized_{anon_tag}@deleted.internal"
    customer.company = "Entidad Anonimizada"
    customer.document_id = None
    customer.locality = "Ubicación Suprimida"
    customer.notes = "[DATOS PERSONALES SUPRIMIDOS CONFORME A LEY 25.326]"

    # Anonimizar contenido de interacciones pasadas
    for act in customer.activities:
        act.summary = "[INTERACCION ANONIMIZADA]"
        act.content = None

    session.flush()
    log_audit_event(
        session,
        "ANONYMIZE_DATA_SUBJECT",
        "Customer",
        customer.id,
        user=username,
        new_data={"anon_tag": anon_tag, "reason": "Ley 25.326 Art. 16"},
    )
    logger.warning(f"Titular de datos ID {customer_id} ({old_phone}) fue anonimizado exitosamente.")
    return True


def export_customer_dossier(
    session: Session,
    customer_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> Dict[str, Any]:
    """
    Genera el expediente completo de datos del titular (SAR - Subject Access Request)
    conforme al Derecho de Acceso de la Ley 25.326.
    """
    customer = get_customer_by_id(session, customer_id, user_actor)
    if not customer:
        raise ValueError("Cliente no encontrado o acceso no autorizado.")

    _, username, _ = _extract_user_context(user_actor, session)
    log_audit_event(session, "SAR_EXPORT", "Customer", customer.id, user=username)

    return {
        "titular": {
            "id": customer.id,
            "nombre": customer.full_name,
            "telefono": customer.phone,
            "email": customer.email,
            "empresa": customer.company,
            "documento": customer.document_id,
            "provincia": customer.province,
            "localidad": customer.locality,
            "creado_el": str(customer.created_at),
        },
        "oportunidades": [
            {
                "id": o.id,
                "titulo": o.title,
                "producto": o.product,
                "monto_ars": o.amount_ars,
                "etapa": o.stage,
                "creado_el": str(o.created_at),
            }
            for o in customer.opportunities
        ],
        "interacciones": [
            {
                "id": a.id,
                "canal": a.channel,
                "direccion": a.direction,
                "resumen": a.summary,
                "fecha": str(a.created_at),
            }
            for a in customer.activities
        ],
    }


# =========================================================================
# MOTOR PROACTIVO DE PROPUESTAS CRM (PATRÓN LIGHTFIELD / HUMAN-IN-THE-LOOP)
# =========================================================================
def create_crm_proposal(
    session: Session,
    customer_id: int,
    proposal_type: str,
    suggested_value: str,
    rationale: str,
    source_quote: str,
    current_value: Optional[str] = None,
    activity_log_id: Optional[int] = None,
    confidence_score: float = 1.0,
) -> PendingCRMProposal:
    """Crea una nueva propuesta generada por la IA local para revisión del usuario."""
    proposal = PendingCRMProposal(
        customer_id=customer_id,
        activity_log_id=activity_log_id,
        proposal_type=proposal_type,
        current_value=current_value,
        suggested_value=suggested_value,
        rationale=rationale,
        source_quote=source_quote,
        confidence_score=confidence_score,
        status="PENDING",
        created_at=utc_now(),
    )
    session.add(proposal)
    session.flush()
    return proposal


def get_pending_proposals(
    session: Session,
    customer_id: Optional[int] = None,
    status: str = "PENDING",
) -> List[PendingCRMProposal]:
    """Obtiene las propuestas pendientes de revisión para un cliente o para todo el CRM."""
    query = session.query(PendingCRMProposal)
    if customer_id is not None:
        query = query.filter(PendingCRMProposal.customer_id == customer_id)
    if status:
        query = query.filter(PendingCRMProposal.status == status)
    return query.order_by(desc(PendingCRMProposal.created_at)).all()


def apply_crm_proposal(
    session: Session,
    proposal_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> bool:
    """
    Aplica una propuesta validada por el humano:
    - STAGE_UPDATE: Actualiza el estado del cliente y de su oportunidad comercial activa.
    - COMMITMENT_TASK: Crea una tarea operativa con vencimiento y responsable asignado.
    - DEAL_RISK: Registra una alerta en notas y en el registro de actividad.
    """
    proposal = session.query(PendingCRMProposal).filter(PendingCRMProposal.id == proposal_id).first()
    if not proposal or proposal.status != "PENDING":
        return False

    customer = session.query(Customer).filter(Customer.id == proposal.customer_id).first()
    if not customer:
        return False

    user_id, username, _ = _extract_user_context(user_actor, session)

    if proposal.proposal_type == "STAGE_UPDATE":
        customer.status = proposal.suggested_value
        customer.updated_at = utc_now()
        # Si tiene oportunidades abiertas, actualizar su etapa
        opps = session.query(Opportunity).filter(Opportunity.customer_id == customer.id).all()
        for opp in opps:
            opp.stage = proposal.suggested_value
            opp.updated_at = utc_now()

        # Registrar en historial
        act = ActivityLog(
            customer_id=customer.id,
            user_id=user_id,
            channel="SYSTEM",
            direction="INBOUND",
            summary=f"Etapa actualizada a {proposal.suggested_value} (IA Aprobada)",
            content=f"Motivo: {proposal.rationale}\nEvidencia: \"{proposal.source_quote}\"",
            created_at=utc_now(),
        )
        session.add(act)

    elif proposal.proposal_type == "COMMITMENT_TASK":
        task = Task(
            customer_id=customer.id,
            assigned_user_id=customer.assigned_user_id or user_id,
            title=proposal.suggested_value,
            task_type="PRESUPUESTO" if "cotiz" in proposal.suggested_value.lower() or "presupuest" in proposal.suggested_value.lower() else "WHATSAPP",
            priority="ALTA" if proposal.confidence_score >= 0.85 else "MEDIA",
            status="PENDIENTE",
            due_date=utc_now() + datetime.timedelta(days=2),
            created_at=utc_now(),
        )
        session.add(task)

    elif proposal.proposal_type == "DEAL_RISK":
        act = ActivityLog(
            customer_id=customer.id,
            user_id=user_id,
            channel="NOTE",
            direction="INBOUND",
            summary=f"Alerta de Riesgo: {proposal.suggested_value}",
            content=f"Detalle: {proposal.rationale}\nEvidencia detectada: \"{proposal.source_quote}\"",
            created_at=utc_now(),
        )
        session.add(act)

    proposal.status = "APPROVED"
    proposal.reviewed_at = utc_now()
    log_audit_event(session, "PROPOSAL_APPLY", "PendingCRMProposal", proposal.id, user=username)
    return True


def reject_crm_proposal(
    session: Session,
    proposal_id: int,
    user_actor: Optional[User | Dict[str, Any] | str] = None,
) -> bool:
    """Descarta una propuesta sugerida por la IA marcándola como REJECTED."""
    proposal = session.query(PendingCRMProposal).filter(PendingCRMProposal.id == proposal_id).first()
    if not proposal or proposal.status != "PENDING":
        return False

    _, username, _ = _extract_user_context(user_actor, session)
    proposal.status = "REJECTED"
    proposal.reviewed_at = utc_now()
    log_audit_event(session, "PROPOSAL_REJECT", "PendingCRMProposal", proposal.id, user=username)
    return True

