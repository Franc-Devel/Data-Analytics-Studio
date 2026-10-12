"""
FAUVOR Analytics - Paquete de Vistas Modulares para la Interfaz de Usuario (Streamlit).
"""

from finance_app.views.auth_view import (
    render_login_form,
    render_user_sidebar_badge,
    render_user_header_badge,
    logout_user,
    init_auth_session,
)
from finance_app.views.crm_view import (
    render_crm_view,
)
from finance_app.views.admin_view import (
    render_admin_view,
)
from finance_app.views.whatsapp_view import (
    render_whatsapp_view,
)
from finance_app.views.executive_view import (
    render_executive_view,
    render_kpi_card,
)
from finance_app.views.reports_view import (
    render_reports_view,
)
from finance_app.views.campaigns_view import (
    render_campaigns_view,
)
from finance_app.views.ai_reports_view import (
    render_ai_reports_view,
)

__all__ = [
    "render_login_form",
    "render_user_sidebar_badge",
    "render_user_header_badge",
    "logout_user",
    "init_auth_session",
    "render_crm_view",
    "render_admin_view",
    "render_whatsapp_view",
    "render_executive_view",
    "render_kpi_card",
    "render_reports_view",
    "render_campaigns_view",
    "render_ai_reports_view",
]

