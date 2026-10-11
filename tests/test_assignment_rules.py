"""
Pruebas unitarias para el motor de reglas automáticas de asignación (finance_app/services/assignment_rules.py).
"""

from finance_app.db.session import get_db_session, reset_db
from finance_app.db.auth_service import create_user
from finance_app.db.crm_service import create_or_update_customer
from finance_app.services.assignment_rules import (
    create_assignment_rule,
    evaluate_and_assign_lead,
)


def test_assignment_rules_evaluation():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        jony = create_user(session, "jony_rule", "jony_rule@test.com", "SecurePassword#2026", "Jony Closer", "closer")
        luisa = create_user(session, "luisa_rule", "luisa_rule@test.com", "SecurePassword#2026", "Luisa Closer", "closer")

        # Regla 1: Sentek -> Jony
        create_assignment_rule(session, "Sentek -> Jony", jony.id, product_line="Sentek", priority_order=1)
        # Regla 2: Jardinería -> Luisa
        create_assignment_rule(session, "Jardinería -> Luisa", luisa.id, product_line="Jardinería", priority_order=2)

        # Lead 1: Sentek
        lead_sentek, _ = create_or_update_customer(session, "+54911111111", "Agro Campo", "Sentek")
        assigned_u1 = evaluate_and_assign_lead(session, lead_sentek)
        assert assigned_u1 is not None
        assert assigned_u1.id == jony.id
        assert lead_sentek.assigned_user_id == jony.id

        # Lead 2: Jardinería
        lead_jard, _ = create_or_update_customer(session, "+54922222222", "Vivero Verde", "Jardinería")
        assigned_u2 = evaluate_and_assign_lead(session, lead_jard)
        assert assigned_u2 is not None
        assert assigned_u2.id == luisa.id
        assert lead_jard.assigned_user_id == luisa.id

        # Lead 3: Producto sin regla
        lead_otro, _ = create_or_update_customer(session, "+54933333333", "Otro Rubro", "Consultoría General")
        assigned_u3 = evaluate_and_assign_lead(session, lead_otro)
        assert assigned_u3 is None
