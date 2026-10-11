"""
Nexo Analytics - Motor de Reglas Automáticas de Asignación de Leads
Distribuye prospectos entre closers según línea de producto, geomarketing y scoring.
"""

from __future__ import annotations
from typing import Optional, List
from sqlalchemy.orm import Session

from finance_app.db.models import Customer, AssignmentRule, User
from finance_app.db.audit_service import log_audit_event
from finance_app.logging_config import get_logger

logger = get_logger("assignment_rules")


def create_assignment_rule(
    session: Session,
    name: str,
    assigned_user_id: int,
    product_line: Optional[str] = None,
    province_or_region: Optional[str] = None,
    min_lead_score: int = 0,
    priority_order: int = 1,
) -> AssignmentRule:
    """Crea una nueva regla de asignación."""
    rule = AssignmentRule(
        name=name.strip(),
        assigned_user_id=assigned_user_id,
        product_line=product_line.strip() if product_line else None,
        province_or_region=province_or_region.strip() if province_or_region else None,
        min_lead_score=min_lead_score,
        priority_order=priority_order,
        is_active=True,
    )
    session.add(rule)
    session.flush()
    logger.info(f"Regla de asignación creada: '{rule.name}' -> Usuario ID {assigned_user_id}")
    return rule


def evaluate_and_assign_lead(
    session: Session,
    customer: Customer,
    user_actor: Optional[User | str] = None,
) -> Optional[User]:
    """
    Evalúa todas las reglas activas ordenadas por prioridad y asigna el lead al closer correspondiente.
    Retorna el User asignado o None si ninguna regla coincidió.
    """
    rules = (
        session.query(AssignmentRule)
        .filter(AssignmentRule.is_active == True)
        .order_by(AssignmentRule.priority_order.asc())
        .all()
    )

    cust_prod = (customer.product_line or "").upper()
    cust_prov = (customer.province or "").upper()
    cust_reg = (customer.region or "").upper()
    cust_score = customer.lead_score or 0

    for rule in rules:
        # 1. Filtro por score mínimo
        if cust_score < rule.min_lead_score:
            continue

        # 2. Filtro por producto (si la regla lo define)
        if rule.product_line:
            r_prod = rule.product_line.upper()
            if r_prod not in cust_prod:
                continue

        # 3. Filtro por provincia o región
        if rule.province_or_region:
            r_geo = rule.province_or_region.upper()
            if r_geo not in cust_prov and r_geo not in cust_reg:
                continue

        # ¡Coincidencia encontrada!
        assigned_user = session.query(User).filter(User.id == rule.assigned_user_id, User.is_active == True).first()
        if assigned_user:
            customer.assigned_user_id = assigned_user.id
            session.flush()
            log_audit_event(
                session,
                "AUTO_ASSIGN",
                "Customer",
                customer.id,
                user=user_actor,
                new_data={"rule_name": rule.name, "assigned_closer": assigned_user.username},
            )
            logger.info(f"Lead {customer.full_name} ({customer.phone}) asignado a {assigned_user.full_name} por regla '{rule.name}'")
            return assigned_user

    return None


def seed_default_assignment_rules(session: Session) -> None:
    """Crea reglas de asignación estándar si no existe ninguna."""
    count = session.query(AssignmentRule).count()
    if count > 0:
        return

    users = {u.username: u for u in session.query(User).all()}
    
    # Asignar según closers históricos
    if "jony" in users:
        create_assignment_rule(session, "Regla Sentek & Davis -> Jony", users["jony"].id, product_line="Sentek", priority_order=1)
        create_assignment_rule(session, "Regla Davis -> Jony", users["jony"].id, product_line="Davis", priority_order=2)

    if "luisa" in users:
        create_assignment_rule(session, "Regla Jardinería & Galcon -> Luisa", users["luisa"].id, product_line="Jardinería", priority_order=3)

    if "sergio" in users:
        create_assignment_rule(session, "Regla GSI & Agro -> Sergio", users["sergio"].id, product_line="GSI", priority_order=4)
        create_assignment_rule(session, "Regla Raphael -> Sergio", users["sergio"].id, product_line="Raphael", priority_order=5)

    session.flush()
    logger.info("Reglas de asignación por defecto creadas exitosamente.")
