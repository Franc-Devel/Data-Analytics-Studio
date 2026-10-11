"""
Nexo Analytics - Paquete de Persistencia Relacional y Modelos de Datos.
"""

from finance_app.db.session import (
    Base,
    get_engine,
    get_session_factory,
    get_db_session,
    init_db,
    reset_db,
)
from finance_app.db.models import (
    User,
    Customer,
    Opportunity,
    Task,
    ActivityLog,
    AuditLog,
    AssignmentRule,
    WhatsAppQueueMessage,
)
from finance_app.db.auth_service import (
    hash_password,
    verify_password,
    authenticate_user,
    create_user,
    has_permission,
    seed_default_users_if_needed,
    ROLE_PERMISSIONS,
)
from finance_app.db.crm_service import (
    create_or_update_customer,
    get_customer_by_id,
    get_customer_by_phone,
    search_customers,
    create_opportunity,
    update_opportunity_stage,
    get_opportunities_by_closer,
    create_task,
    complete_task,
    get_pending_tasks,
    log_customer_activity,
)
from finance_app.db.audit_service import (
    log_audit_event,
    get_audit_trail,
)
from finance_app.db.excel_sync import (
    import_leads_excel_to_db,
    import_commercial_excel_to_db,
    export_db_customers_to_dataframe,
)

__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "init_db",
    "User",
    "Customer",
    "Opportunity",
    "Task",
    "ActivityLog",
    "AuditLog",
    "AssignmentRule",
    "WhatsAppQueueMessage",
    "hash_password",
    "verify_password",
    "authenticate_user",
    "create_user",
    "has_permission",
    "seed_default_users_if_needed",
    "ROLE_PERMISSIONS",
    "create_or_update_customer",
    "get_customer_by_id",
    "get_customer_by_phone",
    "search_customers",
    "create_opportunity",
    "update_opportunity_stage",
    "get_opportunities_by_closer",
    "create_task",
    "complete_task",
    "get_pending_tasks",
    "log_customer_activity",
    "log_audit_event",
    "get_audit_trail",
    "import_leads_excel_to_db",
    "import_commercial_excel_to_db",
    "export_db_customers_to_dataframe",
]
