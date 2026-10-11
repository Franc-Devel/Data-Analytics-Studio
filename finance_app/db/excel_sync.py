"""
Nexo Analytics - Servicio de Sincronización e Importación/Exportación Excel <-> Base de Datos
Permite migrar y mantener sincronizados los datasets Excel con el esquema relacional SQL.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session

from finance_app.db.models import Customer, Opportunity, ActivityLog, User
from finance_app.db.crm_service import create_or_update_customer, create_opportunity, log_customer_activity
from finance_app.db.audit_service import log_audit_event
from finance_app.lead_intelligence import load_and_enrich_leads
from finance_app.commercial_analytics import load_and_analyze_commercial_data
from finance_app.logging_config import get_logger

logger = get_logger("excel_sync")


def import_leads_excel_to_db(
    session: Session,
    excel_source: str | Path | Any,
    user_actor: Optional[User | str] = None,
) -> Tuple[int, int]:
    """
    Importa masivamente los leads de un archivo Excel a la base de datos relacional.
    Retorna (creados, actualizados).
    """
    sheets = load_and_enrich_leads(excel_source)
    if not sheets or "Leeds" not in sheets:
        logger.warning("No se encontraron hojas válidas para importar a la base de datos.")
        return 0, 0

    df_leads = sheets["Leeds"]
    created_count = 0
    updated_count = 0

    for _, row in df_leads.iterrows():
        phone = str(row.get("Telefono", "")).strip()
        if not phone or phone.lower() in ("nan", "none", ""):
            continue

        name = str(row.get("Contacto", "Prospecto sin nombre")).strip()
        prod = str(row.get("Linea_Producto", "General")).strip()
        prov = str(row.get("Provincia_Detectada", row.get("Provincia", ""))).strip()
        loc = str(row.get("Localidad_Detectada", row.get("Localidad", ""))).strip()
        reg = str(row.get("Region_Geografica", row.get("Region", ""))).strip()
        score = int(row.get("Lead_Score", 50))
        seg = str(row.get("Segmento_Lead", row.get("Estado_Lead", "WARM"))).strip()
        rem_id = str(row.get("ID_Lead", "")).strip()
        consulta = str(row.get("Consulta_Detalle", row.get("Consulta_Original", ""))).strip()

        # Determinar status
        status = "NUEVO"
        if bool(row.get("Calificado", False)):
            status = "CALIFICADO"
        elif bool(row.get("Convertido_Derivado", False)):
            status = "COTIZADO"

        cust, was_created = create_or_update_customer(
            session=session,
            phone=phone,
            full_name=name,
            product_line=prod,
            province=prov if prov and prov != "nan" else None,
            locality=loc if loc and loc != "nan" else None,
            region=reg if reg and reg != "nan" else None,
            lead_score=score,
            segment=seg,
            status=status,
            remote_id=rem_id if rem_id and rem_id != "nan" else None,
            notes=consulta if consulta and consulta != "nan" else None,
            user_actor=user_actor,
        )

        if pd.notna(row.get("Fecha_Primer_Contacto")):
            try:
                cust.first_contact_at = pd.to_datetime(row.get("Fecha_Primer_Contacto")).to_pydatetime()
            except Exception:
                pass
        if pd.notna(row.get("Fecha_Ultimo_Contacto")):
            try:
                cust.last_contact_at = pd.to_datetime(row.get("Fecha_Ultimo_Contacto")).to_pydatetime()
            except Exception:
                pass
        if pd.notna(row.get("Cant_Contactos")):
            try:
                cust.total_contacts = int(row.get("Cant_Contactos"))
            except Exception:
                pass

        if was_created:
            created_count += 1
            if consulta and consulta != "nan":
                log_customer_activity(
                    session=session,
                    customer_id=cust.id,
                    summary="Ingesta inicial de consulta desde Excel CRM",
                    channel="NOTE",
                    direction="INBOUND",
                    content=consulta,
                )
        else:
            updated_count += 1

    session.flush()
    log_audit_event(
        session,
        "IMPORT",
        "Customer",
        entity_id=f"Total: {created_count + updated_count}",
        user=user_actor,
        new_data={"created": created_count, "updated": updated_count},
    )
    logger.info(f"Sincronización Excel -> BD completada: {created_count} creados, {updated_count} actualizados.")
    return created_count, updated_count


def import_commercial_excel_to_db(
    session: Session,
    excel_source: str | Path | Any,
    user_actor: Optional[User | str] = None,
) -> int:
    """
    Importa las oportunidades y cotizaciones del archivo Comercial.xlsx a la base de datos relacional.
    Retorna la cantidad de oportunidades importadas.
    """
    import re
    res = load_and_analyze_commercial_data(excel_source)
    if not res or res.df_opportunities.empty:
        return 0

    opp_count = 0
    for _, row in res.df_opportunities.iterrows():
        title = str(row.get("Cliente", row.get("Empresa_o_Cliente", "Oportunidad Comercial"))).strip()
        prod = str(row.get("Producto", "General")).strip()
        
        try:
            monto_val = row.get("Monto_Cotizado", row.get("Monto_Cotizado_ARS", 0.0))
            monto = float(monto_val) if pd.notna(monto_val) else 0.0
        except Exception:
            monto = 0.0

        prob_str = str(row.get("Prob_Cierre", "")).lower().strip()
        if any(k in prob_str for k in ("ganad", "100", "despach")) or prob_str in ("1", "1.0"):
            etapa = "CERRADO_GANADO"
            prob_pct = 100
        elif any(k in prob_str for k in ("perdid", "no interesado")) or prob_str in ("0", "0.0", "no"):
            etapa = "CERRADO_PERDIDO"
            prob_pct = 0
        elif "negoc" in prob_str:
            etapa = "NEGOCIACION"
            prob_pct = 75
        elif any(k in prob_str for k in ("0.8", "0.9", "80", "90")):
            etapa = "NEGOCIACION"
            prob_pct = 85
        elif any(k in prob_str for k in ("0.5", "50")):
            etapa = "PROPUESTA_ENVIADA"
            prob_pct = 50
        elif any(k in prob_str for k in ("0.2", "0.3", "20", "30")):
            etapa = "PROPUESTA_ENVIADA"
            prob_pct = 30
        else:
            etapa = "PROPUESTA_ENVIADA"
            prob_pct = 40

        closer_name = str(row.get("Derivado_A", row.get("Closer_Asignado", ""))).strip()

        # Buscar usuario closer correspondiente
        closer_user = None
        if closer_name and closer_name not in ("Sin Asignar", "nan", ""):
            for part in ["Jony", "Luisa", "Agustina", "Sergio", "Alon"]:
                if part.lower() in closer_name.lower():
                    closer_user = session.query(User).filter(User.full_name.ilike(f"%{part}%")).first()
                    if closer_user:
                        break
            if not closer_user:
                closer_user = session.query(User).filter(User.full_name.ilike(f"%{closer_name}%")).first()

        comentarios = str(row.get("Comentarios_Tecnicos", "")).strip()

        # Detectar nombre de empresa en comentarios
        company = None
        if "empresa:" in comentarios.lower():
            m_comp = re.search(r"empresa:\s*([^\n\.,\-]+)", comentarios, re.IGNORECASE)
            if m_comp:
                company = m_comp.group(1).strip()
        elif "grupo la zulema" in comentarios.lower():
            company = "Grupo La Zulema"
        elif "vajuca agro" in comentarios.lower():
            company = "Vajuca Agro S.A."
        elif "cifsa" in comentarios.lower():
            company = "CIFSA"
        elif "fresas mdq" in comentarios.lower():
            company = "Fresas MDQ"
        elif "daterra" in comentarios.lower():
            company = "DATERRA SRL"
        elif "alif agro" in comentarios.lower():
            company = "Alif Agro"
        elif "sygea" in comentarios.lower():
            company = "SyGea"

        # Vincular a un cliente existente o nuevo
        contact_phone = str(row.get("Contacto", "")).strip()
        if not contact_phone or contact_phone in ("nan", "None", ""):
            contact_phone = f"+5490000{opp_count:04d}"

        customer, _ = create_or_update_customer(
            session=session,
            phone=contact_phone,
            full_name=title,
            product_line=prod,
            company=company,
            status="COTIZADO",
            user_actor=user_actor,
        )
        if company and not customer.company:
            customer.company = company

        create_opportunity(
            session=session,
            customer_id=customer.id,
            title=f"Cotización {prod} - {title}",
            product=prod,
            amount_ars=monto,
            stage=etapa,
            probability_pct=prob_pct,
            notes=comentarios if comentarios and comentarios != "nan" else None,
            assigned_closer_id=closer_user.id if closer_user else None,
            user_actor=user_actor,
        )

        if comentarios and comentarios != "nan":
            log_customer_activity(
                session=session,
                customer_id=customer.id,
                summary=f"Cotización {prod} ({etapa})",
                channel="NOTE",
                direction="OUTBOUND",
                content=comentarios,
            )

        opp_count += 1

    session.flush()
    log_audit_event(session, "IMPORT", "Opportunity", entity_id=f"Total: {opp_count}", user=user_actor)
    logger.info(f"Oportunidades comerciales importadas a BD: {opp_count} registros.")
    return opp_count


def export_db_customers_to_dataframe(session: Session) -> pd.DataFrame:
    """Exporta todos los clientes de la base de datos a un DataFrame normalizado."""
    customers = session.query(Customer).order_by(Customer.id.asc()).all()
    records = []
    for c in customers:
        closer_name = c.assigned_user.full_name if c.assigned_user else "Sin Asignar"
        records.append({
            "ID_Cliente": c.id,
            "ID_Remoto": c.remote_id or "",
            "Nombre_Completo": c.full_name,
            "Telefono": c.phone,
            "Email": c.email or "",
            "Empresa": c.company or "",
            "Linea_Producto": c.product_line or "",
            "Provincia": c.province or "",
            "Localidad": c.locality or "",
            "Region": c.region or "",
            "Lead_Score": c.lead_score,
            "Segmento": c.segment,
            "Estado": c.status,
            "Closer_Asignado": closer_name,
            "Total_Contactos": c.total_contacts,
            "Primer_Contacto": c.first_contact_at.strftime("%Y-%m-%d %H:%M") if c.first_contact_at else "",
            "Ultimo_Contacto": c.last_contact_at.strftime("%Y-%m-%d %H:%M") if c.last_contact_at else "",
            "Notas": c.notes or "",
        })
    return pd.DataFrame(records)
