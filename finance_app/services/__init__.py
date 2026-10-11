"""
Nexo Analytics - Paquete de Servicios de Automatización y Mensajería.
"""

from finance_app.services.assignment_rules import (
    create_assignment_rule,
    evaluate_and_assign_lead,
    seed_default_assignment_rules,
)
from finance_app.services.whatsapp_queue import (
    enqueue_whatsapp_message,
    process_next_queue_batch,
    get_queue_metrics,
)
from finance_app.services.calendar_service import (
    generate_meeting_ics,
)
from finance_app.services.ai_service import (
    LeadMessageAnalysis,
    get_ai_status,
    is_ai_available,
    analyze_whatsapp_message,
    analyze_conversation_history,
    ask_crm_assistant,
    run_lightfield_analysis,
    process_document_with_ai,
    save_document_to_database,
)
from finance_app.services.airtable_auth_service import (
    authenticate_user_with_airtable,
    fetch_all_users,
    find_user_by_email,
    create_airtable_user,
    activate_user_2fa,
    reset_password_via_2fa,
)
from finance_app.services.meta_ads_service import (
    MetaCampaignInsight,
    fetch_meta_ads_insights,
    get_meta_ads_status,
    build_commercial_dataframe_from_meta,
    generate_demo_meta_campaigns,
    infer_product_from_campaign_name,
    merge_meta_insights_into_commercial_result,
)

__all__ = [
    "create_assignment_rule",
    "evaluate_and_assign_lead",
    "seed_default_assignment_rules",
    "enqueue_whatsapp_message",
    "process_next_queue_batch",
    "get_queue_metrics",
    "generate_meeting_ics",
    "LeadMessageAnalysis",
    "get_ai_status",
    "is_ai_available",
    "analyze_whatsapp_message",
    "analyze_conversation_history",
    "ask_crm_assistant",
    "run_lightfield_analysis",
    "process_document_with_ai",
    "save_document_to_database",
    "authenticate_user_with_airtable",
    "fetch_all_users",
    "find_user_by_email",
    "create_airtable_user",
    "activate_user_2fa",
    "reset_password_via_2fa",
    "MetaCampaignInsight",
    "fetch_meta_ads_insights",
    "get_meta_ads_status",
    "build_commercial_dataframe_from_meta",
    "generate_demo_meta_campaigns",
    "infer_product_from_campaign_name",
    "merge_meta_insights_into_commercial_result",
]



