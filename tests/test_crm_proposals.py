"""
Pruebas automatizadas para el Motor Proactivo de Propuestas CRM (Patrón Lightfield CRM / Human-in-the-Loop).
Valida la creación, persistencia, aprobación y descarte de propuestas de etapa, compromisos y riesgos.
"""

import pytest
from finance_app.db.session import get_db_session, init_db
from finance_app.db.models import Customer, Opportunity, Task, ActivityLog, PendingCRMProposal, User
from finance_app.db.crm_service import (
    create_or_update_customer,
    create_opportunity,
    create_crm_proposal,
    get_pending_proposals,
    apply_crm_proposal,
    reject_crm_proposal,
)
from finance_app.services.ai_service import run_lightfield_analysis


@pytest.fixture(autouse=True)
def setup_database():
    """Inicializa la base de datos de pruebas."""
    init_db()


def test_create_and_query_proposals():
    """Valida la creación de una propuesta y su consulta filtrada por estado y cliente."""
    with get_db_session() as session:
        # Crear cliente de prueba
        customer, _ = create_or_update_customer(
            session=session,
            phone="+5493519876543",
            full_name="Pedro Gonzalez",
            product_line="Sentek",
            user_actor="admin",
        )
        session.commit()

        # Crear propuesta
        prop = create_crm_proposal(
            session=session,
            customer_id=customer.id,
            proposal_type="STAGE_UPDATE",
            suggested_value="COTIZADO",
            rationale="El cliente solicitó presupuesto formal de sondas.",
            source_quote="mandame la cotizacion porfa",
            current_value="NUEVO",
            confidence_score=0.95,
        )
        session.commit()

        pending = get_pending_proposals(session, customer_id=customer.id)
        assert len(pending) >= 1
        assert pending[0].suggested_value == "COTIZADO"
        assert pending[0].status == "PENDING"
        assert pending[0].confidence_score == 0.95


def test_apply_stage_update_proposal():
    """Valida que la aprobación de una propuesta STAGE_UPDATE mute el estado del cliente y de su oportunidad."""
    with get_db_session() as session:
        customer, _ = create_or_update_customer(
            session=session,
            phone="+5491144556677",
            full_name="Carlos Ruiz",
            product_line="Davis",
            user_actor="admin",
        )
        customer.status = "EN_SEGUIMIENTO"
        opp = create_opportunity(
            session=session,
            customer_id=customer.id,
            title="Estación Davis Vantage Pro 2",
            product="Davis",
            stage="EN_SEGUIMIENTO",
            user_actor="admin",
        )
        session.commit()

        prop = create_crm_proposal(
            session=session,
            customer_id=customer.id,
            proposal_type="STAGE_UPDATE",
            suggested_value="COTIZADO",
            rationale="Presupuesto formal solicitado.",
            source_quote="pasame precio con flete",
            current_value="EN_SEGUIMIENTO",
        )
        session.commit()

        ok = apply_crm_proposal(session, prop.id, user_actor="admin")
        assert ok is True
        session.commit()

        # Recargar y verificar
        refreshed_cust = session.query(Customer).filter_by(id=customer.id).one()
        assert refreshed_cust.status == "COTIZADO"
        refreshed_opp = session.query(Opportunity).filter_by(id=opp.id).one()
        assert refreshed_opp.stage == "COTIZADO"

        # Verificar que la propuesta quedó aprobada
        refreshed_prop = session.query(PendingCRMProposal).filter_by(id=prop.id).one()
        assert refreshed_prop.status == "APPROVED"
        assert refreshed_prop.reviewed_at is not None


def test_apply_commitment_task_proposal():
    """Valida que la aprobación de un compromiso genere una Task en el sistema."""
    with get_db_session() as session:
        customer, _ = create_or_update_customer(
            session=session,
            phone="+5493415556677",
            full_name="Mariana Lopez",
            product_line="Raphael",
            user_actor="admin",
        )
        session.commit()

        prop = create_crm_proposal(
            session=session,
            customer_id=customer.id,
            proposal_type="COMMITMENT_TASK",
            suggested_value="Enviar ficha técnica de válvulas hidráulicas",
            rationale="Compromiso acordado para mañana.",
            source_quote="te mando la ficha tecnica mañana",
            confidence_score=0.9,
        )
        session.commit()

        ok = apply_crm_proposal(session, prop.id, user_actor="admin")
        assert ok is True
        session.commit()

        # Verificar tarea creada
        tasks = session.query(Task).filter_by(customer_id=customer.id).all()
        assert len(tasks) >= 1
        assert "ficha técnica" in tasks[-1].title.lower()


def test_reject_proposal():
    """Valida el descarte de propuestas sin alterar los registros del cliente."""
    with get_db_session() as session:
        customer, _ = create_or_update_customer(
            session=session,
            phone="+5493581112233",
            full_name="Santiago Rossi",
            user_actor="admin",
        )
        session.commit()

        prop = create_crm_proposal(
            session=session,
            customer_id=customer.id,
            proposal_type="DEAL_RISK",
            suggested_value="Objeción de Costo",
            rationale="Cliente duda del precio.",
            source_quote="muy caro",
        )
        session.commit()

        ok = reject_crm_proposal(session, prop.id, user_actor="admin")
        assert ok is True
        session.commit()

        refreshed = session.query(PendingCRMProposal).filter_by(id=prop.id).one()
        assert refreshed.status == "REJECTED"


def test_run_lightfield_analysis_fallback():
    """Valida la generación de propuestas de contingencia basada en heurística."""
    history = [
        {"sender_name": "Cliente", "text": "Hola, cuanto sale la estacion meteorologica Davis?"},
        {"is_from_me": True, "text": "Hola, te paso el presupuesto formal hoy."},
    ]
    res = run_lightfield_analysis(history, current_stage="NUEVO")
    assert isinstance(res, dict)
    assert "proposals" in res
    assert len(res["proposals"]) >= 1
    assert any(p["type"] == "STAGE_UPDATE" for p in res["proposals"])
