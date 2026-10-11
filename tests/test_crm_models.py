"""
Pruebas unitarias para el modelo CRM, Ficha 360, Pipeline, Tareas y Auditoría (finance_app/db/crm_service.py).
"""

import datetime
from finance_app.db.session import get_db_session, reset_db
from finance_app.db.models import User, Customer, Opportunity, Task, ActivityLog, AuditLog
from finance_app.db.crm_service import (
    create_or_update_customer,
    get_customer_by_id,
    get_customer_by_phone,
    search_customers,
    create_opportunity,
    update_opportunity_stage,
    create_task,
    complete_task,
    get_pending_tasks,
    log_customer_activity,
)
from finance_app.db.audit_service import get_audit_trail


def test_customer_creation_update_and_search():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        # 1. Crear cliente
        cust, created = create_or_update_customer(
            session=session,
            phone="+5493512345678",
            full_name="Carlos Martinez",
            product_line="Sentek",
            province="Córdoba",
            locality="Villa María",
            lead_score=85,
            segment="HOT",
            user_actor="admin",
        )
        assert created is True
        assert cust.id is not None
        assert cust.lead_score == 85

        # 2. Actualizar cliente existente por teléfono
        cust2, created2 = create_or_update_customer(
            session=session,
            phone="+5493512345678",
            full_name="Carlos Martinez (Agro)",
            lead_score=90,
            status="CALIFICADO",
            user_actor="admin",
        )
        assert created2 is False
        assert cust2.id == cust.id
        assert cust2.full_name == "Carlos Martinez (Agro)"
        assert cust2.lead_score == 90
        assert cust2.total_contacts == 2

        # 3. Búsqueda
        res1 = search_customers(session, query="Villa María")
        assert len(res1) == 1
        assert res1[0].id == cust.id

        res2 = search_customers(session, product_line="Sentek")
        assert len(res2) == 1

        res_none = search_customers(session, query="Inexistente")
        assert len(res_none) == 0


def test_opportunity_lifecycle_and_pipeline():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        cust, _ = create_or_update_customer(session, "+5491122334455", "Lucia Fernandez", "Davis")
        
        # Crear oportunidad
        opp = create_opportunity(
            session=session,
            customer_id=cust.id,
            title="Estación Meteorológica Vantage Pro2",
            product="Davis",
            amount_ars=750000.0,
            stage="PROSPECCION",
        )
        assert opp.id is not None
        assert opp.probability_pct == 20

        # Avanzar etapa
        opp_updated = update_opportunity_stage(session, opp.id, "PROPUESTA_ENVIADA")
        assert opp_updated.stage == "PROPUESTA_ENVIADA"
        assert opp_updated.probability_pct == 70

        # Cerrar ganada
        opp_won = update_opportunity_stage(session, opp.id, "CERRADO_GANADO")
        assert opp_won.probability_pct == 100


def test_task_management_and_completion():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        cust, _ = create_or_update_customer(session, "+5493415556677", "Esteban Quito", "GSI")
        
        due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
        task = create_task(session, cust.id, "Llamar para coordinar demo", due, task_type="LLAMADA", priority="ALTA")
        assert task.status == "PENDIENTE"

        pending = get_pending_tasks(session)
        assert len(pending) == 1
        assert pending[0].id == task.id

        # Completar tarea
        done_task = complete_task(session, task.id)
        assert done_task.status == "COMPLETADA"
        assert done_task.completed_at is not None

        assert len(get_pending_tasks(session)) == 0


def test_activity_logging_and_audit_trail():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        cust, _ = create_or_update_customer(session, "+5492614443322", "Mendoza Wines", "Jardinería", user_actor="jony")
        
        act = log_customer_activity(
            session=session,
            customer_id=cust.id,
            summary="Envío de ficha técnica Raphael",
            channel="WHATSAPP",
            direction="OUTBOUND",
            content="Adjunto catálogo 2026...",
        )
        assert act.id is not None

        # Verificar auditoría
        audit_trail = get_audit_trail(session, entity_type="Customer")
        assert len(audit_trail) >= 1
        assert audit_trail[0].action == "CREATE"
        assert audit_trail[0].username == "jony"
