"""
Pruebas unitarias para el motor de base de datos relacional (finance_app/db/session.py).
"""

from finance_app.db.session import get_engine, get_db_session, reset_db
from finance_app.db.models import User, Customer, Opportunity, Task


def test_init_in_memory_db():
    db_url = "sqlite://"
    reset_db(db_url)
    engine = get_engine(db_url)
    assert engine is not None

    with get_db_session(db_url) as session:
        user = User(
            username="db_tester",
            email="tester@consultora.com",
            hashed_password="hash",
            full_name="Tester DB",
            role="admin",
        )
        session.add(user)
        session.flush()

        cust = Customer(
            full_name="Cliente DB Test",
            phone="+5491100001111",
            lead_score=80,
            assigned_user_id=user.id,
        )
        session.add(cust)
        session.flush()

        opp = Opportunity(
            customer_id=cust.id,
            title="Oportunidad DB Test",
            product="Sentek",
            amount_ars=150000.0,
            assigned_closer_id=user.id,
        )
        session.add(opp)
        session.flush()

        task = Task(
            customer_id=cust.id,
            title="Llamar a cliente",
            due_date=cust.created_at,
            assigned_user_id=user.id,
        )
        session.add(task)
        session.flush()

        # Verificaciones relacionales
        assert cust.assigned_user.username == "db_tester"
        assert len(cust.opportunities) == 1
        assert cust.opportunities[0].amount_ars == 150000.0
        assert len(cust.tasks) == 1
