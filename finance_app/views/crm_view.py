"""
FAUVOR Analytics - Vista de CRM Estructurado, Ficha Única 360°, Pipeline y Tareas (Streamlit)
"""

import datetime
import streamlit as st
from sqlalchemy.orm import Session

from finance_app.db.session import get_db_session
from finance_app.db.models import Customer, Opportunity, Task, ActivityLog, User
from finance_app.db.crm_service import (
    search_customers,
    get_customer_by_id,
    create_or_update_customer,
    create_opportunity,
    update_opportunity_stage,
    get_opportunities_by_closer,
    create_task,
    complete_task,
    get_pending_tasks,
    log_customer_activity,
    create_crm_proposal,
    get_pending_proposals,
    apply_crm_proposal,
    reject_crm_proposal,
)
from finance_app.services.ai_service import (
    run_lightfield_analysis,
    get_ai_status,
)
from finance_app.services.airtable_auth_service import is_valid_email

from finance_app.lead_intelligence import build_whatsapp_link


def render_crm_view(current_user: dict):
    """Renderiza la suite completa de CRM estructurado."""
    st.markdown("## Núcleo CRM · Ficha 360°, Pipeline & Tareas")
    st.caption("Gestión relacional integral de prospectos, oportunidades de venta y seguimiento.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Ficha Única de Cliente (360°)",
        "Pipeline Comercial (Kanban)",
        "Tareas & Vencimientos",
        "Nuevo Prospecto / Cliente",
    ])

    # -------------------------------------------------------------
    # TAB 1: FICHA ÚNICA DE CLIENTE 360°
    # -------------------------------------------------------------
    with tab1:
        with get_db_session() as session:
            # Filtros de búsqueda
            col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
            with col_s1:
                search_q = st.text_input("Buscar por Nombre, Teléfono, Localidad o Empresa", placeholder="Ej: Roberto, +54911, Rosario...")
            with col_s2:
                filter_prod = st.selectbox("Línea de Producto", ["Todos", "Sentek", "Davis", "Jardinería", "Raphael", "GSI"])
            with col_s3:
                filter_seg = st.selectbox("Segmento", ["Todos", "HOT", "WARM", "COLD", "REACTIVADO", "DERIVADO"])

            # Consulta a BD con aislamiento por rol
            customers = search_customers(
                session=session,
                query=search_q if search_q else None,
                product_line=filter_prod if filter_prod != "Todos" else None,
                segment=filter_seg if filter_seg != "Todos" else None,
                limit=30,
                user_actor=current_user,
            )

            if not customers:
                st.info("No se encontraron clientes accesibles con los filtros especificados.")
            else:
                cust_options = {f"{c.full_name} ({c.phone}) - {c.product_line or 'General'}": c.id for c in customers}
                selected_label = st.selectbox("Seleccione un Cliente para ver su Ficha 360°:", list(cust_options.keys()))
                selected_id = cust_options[selected_label]
                customer = get_customer_by_id(session, selected_id, user_actor=current_user)

                if customer:
                    st.divider()

                    # Encabezado 360°
                    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
                    with col_h1:
                        st.markdown(f"### {customer.full_name}")
                        st.markdown(f"**Teléfono:** `{customer.phone}` | **Email:** `{customer.email or 'No registrado'}`")
                        st.markdown(f"**Empresa:** {customer.company or 'Particular'} | **Ubicación:** {customer.locality or ''}, {customer.province or 'N/A'} ({customer.region or ''})")

                    with col_h2:
                        score_color = "#ef4444" if customer.lead_score >= 75 else "#f59e0b" if customer.lead_score >= 50 else "#64748b"
                        st.markdown(f"""
                        <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 14px; text-align: center;">
                            <div style="font-size: 14.5px; color: #786451; font-weight: 700; letter-spacing: 0.5px;">LEAD SCORE</div>
                            <div style="font-size: 34px; font-weight: 800; color: {score_color}; margin: 4px 0;">{customer.lead_score}</div>
                            <div style="font-size: 16px; color: {score_color}; font-weight: 700;">{customer.segment}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_h3:
                        closer_name = customer.assigned_user.full_name if customer.assigned_user else "Sin Asignar"
                        st.markdown(f"""
                        <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 14px; text-align: center;">
                            <div style="font-size: 14.5px; color: #786451; font-weight: 700; letter-spacing: 0.5px;">CLOSER ASIGNADO</div>
                            <div style="font-size: 18px; font-weight: 700; color: #895522; margin-top: 4px;">{closer_name}</div>
                            <div style="font-size: 15px; color: #10b981; margin-top: 4px; font-weight: 600;">Estado: {customer.status}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Botón Directo a WhatsApp y Acciones de Privacidad (Ley 25.326)
                    col_act1, col_act2 = st.columns([2, 1])
                    with col_act1:
                        wa_url = build_whatsapp_link(customer.phone, customer.full_name, customer.product_line or "")
                        st.markdown(f"<a href='{wa_url}' target='_blank' style='display: inline-block; background-color: #25D366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 16px; margin-top: 10px;'>Abrir Chat de WhatsApp Directo</a>", unsafe_allow_html=True)

                    with col_act2:
                        if current_user.get("role") in ("admin", "manager"):
                            with st.popover("Privacidad (Ley 25.326)"):
                                st.caption("Gestión de derechos de los titulares de datos.")
                                from finance_app.db.crm_service import export_customer_dossier, anonymize_customer
                                import json
                                dossier = export_customer_dossier(session, customer.id, user_actor=current_user)
                                st.download_button(
                                    "Exportar Expediente (SAR)",
                                    data=json.dumps(dossier, indent=2, ensure_ascii=False),
                                    file_name=f"expediente_sar_titular_{customer.id}.json",
                                    mime="application/json",
                                    use_container_width=True,
                                )
                                if st.button("Suprimir / Anonimizar", key=f"btn_anon_{customer.id}", use_container_width=True):
                                    anonymize_customer(session, customer.id, user_actor=current_user)
                                    session.commit()
                                    st.warning("Titular de datos personales anonimizado.")
                                    st.rerun()

                    # -------------------------------------------------------------
                    # DIAGNÓSTICO COGNITIVO AUTÓNOMO & PROPUESTAS (LIGHTFIELD CRM)
                    # -------------------------------------------------------------
                    with st.expander("Diagnóstico Cognitivo Autónomo & Propuestas Proactivas", expanded=True):
                        ai_status = get_ai_status()
                        col_ai_top1, col_ai_top2 = st.columns([2, 1])
                        with col_ai_top1:
                            st.caption(f"Motor IA: `{ai_status.get('current_model', 'qwen2.5-crm-expert')}`")
                        with col_ai_top2:
                            st.caption(f"Estado: {'Operativo' if ai_status.get('available') else 'Desconectado'}")

                        if st.button("Ejecutar Auditoría de Interacciones Recientes", key=f"btn_cog_audit_{customer.id}", use_container_width=True, type="primary"):
                            with st.status("Analizando interacciones del cliente...", expanded=True) as status_box:
                                st.write("Recuperando mensajes históricos de WhatsApp...")
                                history = []
                                for act in customer.activities:
                                    history.append({
                                        "is_from_me": act.direction == "OUTBOUND",
                                        "summary": act.summary,
                                        "text": act.content or act.summary,
                                        "direction": act.direction,
                                    })
                                if customer.notes:
                                    history.append({"is_from_me": False, "text": customer.notes, "direction": "INBOUND"})

                                st.write(f"Cotejando semánticamente {len(history)} mensajes e interacciones...")
                                st.write("Extrayendo compromisos y evaluando riesgos con IA local (Qwen 2.5 CRM Expert)...")
                                analysis_result = run_lightfield_analysis(
                                    history=history,
                                    client_name=customer.full_name,
                                    current_stage=customer.status,
                                )

                                # Persistir las propuestas generadas en SQLite
                                for p in analysis_result.get("proposals", []):
                                    create_crm_proposal(
                                        session=session,
                                        customer_id=customer.id,
                                        proposal_type=p["type"],
                                        suggested_value=p["suggested_value"],
                                        rationale=p.get("rationale") or p.get("description", ""),
                                        source_quote=p.get("evidence", ""),
                                        current_value=p.get("current_value"),
                                        confidence_score=p.get("confidence", 0.9),
                                    )
                                session.commit()

                                status_box.update(
                                    label="Auditoría cognitiva completada exitosamente",
                                    state="complete",
                                    expanded=False
                                )
                            st.rerun()

                        # Renderizado de Tarjetas de Propuestas Pendientes (Human-in-the-Loop)
                        proposals = get_pending_proposals(session, customer_id=customer.id)
                        if not proposals:
                            st.info("No se registran cambios de etapa pendientes ni compromisos desatendidos.")
                        else:
                            st.markdown("#### Actualizaciones Proactivas Sugeridas (Validación con 1 Clic)")
                            for proposal in proposals:
                                with st.container():
                                    col_info, col_actions = st.columns([0.75, 0.25])
                                    with col_info:
                                        type_labels = {
                                            "STAGE_UPDATE": "Avance de Etapa",
                                            "COMMITMENT_TASK": "Compromiso Comercial",
                                            "DEAL_RISK": "Alerta de Riesgo",
                                        }
                                        label = type_labels.get(proposal.proposal_type, proposal.proposal_type)
                                        st.markdown(f"**[{label}] {proposal.suggested_value}**")
                                        if proposal.source_quote:
                                            st.caption(f"Evidencia textual: *\"{proposal.source_quote}\"*")
                                        st.write(proposal.rationale)
                                    with col_actions:
                                        if st.button("Aprobar ✓", key=f"app_{proposal.id}", use_container_width=True, type="primary"):
                                            apply_crm_proposal(session, proposal.id, current_user)
                                            session.commit()
                                            st.success("✓ Propuesta aplicada al CRM")
                                            st.rerun()
                                        if st.button("Descartar ✕", key=f"rej_{proposal.id}", use_container_width=True):
                                            reject_crm_proposal(session, proposal.id, current_user)
                                            session.commit()
                                            st.info("Propuesta descartada")
                                            st.rerun()
                                st.divider()

                    # Sección de Actividad e Interacciones
                    st.markdown("#### Historial de Interacciones & Actividad Multicanal")
                    activities = customer.activities

                    col_act1, col_act2 = st.columns([2, 1])
                    with col_act1:
                        if not activities:
                            st.info("No hay interacciones registradas aún para este cliente.")
                        else:
                            for act in activities[:10]:
                                direction_tag = " [Entrante]" if act.direction == "INBOUND" else " [Saliente]"
                                st.markdown(f"""
                                <div style="background: rgba(15, 23, 42, 0.7); border-left: 4px solid #895522; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;">
                                    <div style="font-size: 15px; color: #786451; font-weight: 700;"><b>CANAL: {act.channel}{direction_tag}</b> · {act.created_at.strftime('%Y-%m-%d %H:%M')}</div>
                                    <div style="font-size: 17px; font-weight: 600; color: #2B211A; margin-top: 4px;">{act.summary}</div>
                                    {f"<div style='font-size: 16px; color: #cbd5e1; margin-top: 6px; line-height: 1.5;'>{act.content}</div>" if act.content else ""}
                                </div>
                                """, unsafe_allow_html=True)

                    with col_act2:
                        with st.form("form_add_activity"):
                            st.markdown("##### Registrar Interacción")
                            act_channel = st.selectbox("Canal", ["WHATSAPP", "CALL", "MEETING", "EMAIL", "NOTE"])
                            act_direction = st.selectbox("Dirección", ["OUTBOUND", "INBOUND"])
                            act_summary = st.text_input("Resumen", placeholder="Ej: Llamada de seguimiento de presupuesto")
                            act_content = st.text_area("Detalles de la conversación", placeholder="Notas clave...", height=80)
                            submit_act = st.form_submit_button("Guardar Interacción", use_container_width=True)

                            if submit_act:
                                if not act_summary or not act_summary.strip():
                                    st.error("El resumen de la interacción es un campo obligatorio.")
                                else:
                                    log_customer_activity(
                                        session=session,
                                        customer_id=customer.id,
                                        summary=act_summary.strip(),
                                        channel=act_channel,
                                        direction=act_direction,
                                        content=act_content,
                                        user_id=current_user["id"],
                                    )
                                    session.commit()
                                    st.success("Interacción registrada.")
                                    st.rerun()

    # -------------------------------------------------------------
    # TAB 2: PIPELINE COMERCIAL (KANBAN)
    # -------------------------------------------------------------
    with tab2:
        with get_db_session() as session:
            st.markdown("#### Pipeline Comercial de Oportunidades")

            # Formulario para crear oportunidad
            with st.expander("Crear Nueva Oportunidad Comercial", expanded=False):
                with st.form("form_new_opp"):
                    c_col1, c_col2, c_col3 = st.columns(3)
                    with c_col1:
                        opp_title = st.text_input("Título de la Oportunidad", placeholder="Ej: Sonda Sentek 1.2m - Campo Sur")
                        # Lista de clientes accesibles
                        all_custs = search_customers(session=session, user_actor=current_user, limit=100)
                        opp_cust_dict = {f"{c.full_name} ({c.phone})": c.id for c in all_custs}
                        opp_cust_label = st.selectbox("Cliente / Prospecto", list(opp_cust_dict.keys()) if opp_cust_dict else ["Sin clientes"])

                    with c_col2:
                        opp_prod = st.selectbox("Producto", ["Sentek", "Davis", "Jardinería", "Raphael", "GSI"])
                        opp_amount = st.number_input("Monto Estimado ($ ARS)", min_value=0.0, step=50000.0, value=250000.0)

                    with c_col3:
                        opp_stage = st.selectbox("Etapa Inicial", ["PROSPECCION", "CONTACTADO", "REUNION_AGENDADA", "PROPUESTA_ENVIADA", "NEGOCIACION", "CERRADO_GANADO"])
                        # Closers
                        all_closers = session.query(User).filter(User.role.in_(["closer", "admin", "manager"])).all()
                        closer_dict = {u.full_name: u.id for u in all_closers}
                        opp_closer_label = st.selectbox("Closer Asignado", list(closer_dict.keys()))

                    opp_notes = st.text_input("Notas u Observaciones")
                    btn_save_opp = st.form_submit_button("Crear Oportunidad en Pipeline", use_container_width=True)

                    if btn_save_opp:
                        if not opp_title or not opp_title.strip():
                            st.error("El título de la oportunidad es un campo obligatorio.")
                        elif not opp_cust_dict or opp_cust_label == "Sin clientes":
                            st.error("Debe seleccionar un cliente existente para vincular la oportunidad.")
                        else:
                            create_opportunity(
                                session=session,
                                customer_id=opp_cust_dict[opp_cust_label],
                                title=opp_title.strip(),
                                product=opp_prod,
                                amount_ars=opp_amount,
                                stage=opp_stage,
                                assigned_closer_id=closer_dict[opp_closer_label],
                                notes=opp_notes,
                                user_actor=current_user,
                            )
                            session.commit()
                            st.success("Oportunidad agregada al pipeline.")
                            st.rerun()

            # Visualización por columnas Kanban con filtrado seguro
            stages = ["PROSPECCION", "CONTACTADO", "REUNION_AGENDADA", "PROPUESTA_ENVIADA", "NEGOCIACION", "CERRADO_GANADO"]
            cols = st.columns(len(stages))
            all_user_opps = get_opportunities_by_closer(session, closer_id=None, user_actor=current_user)

            for i, stage_name in enumerate(stages):
                with cols[i]:
                    opps = [o for o in all_user_opps if o.stage == stage_name]
                    total_stage_ars = sum(o.amount_ars for o in opps)

                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.95); border-radius: 8px; padding: 10px 8px; text-align: center; border-bottom: 4px solid #895522; margin-bottom: 12px;">
                        <div style="font-size: 15.5px; font-weight: 700; color: #786451; text-transform: uppercase;">{stage_name.replace('_', ' ')}</div>
                        <div style="font-size: 18px; font-weight: 800; color: #2B211A; margin: 4px 0;">${total_stage_ars:,.0f}</div>
                        <div style="font-size: 14.5px; color: #895522; font-weight: 600;">{len(opps)} ops</div>
                    </div>
                    """, unsafe_allow_html=True)

                    for opp in opps:
                        with st.container():
                            st.markdown(f"""
                            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                                <div style="font-size: 16.5px; font-weight: 700; color: #2B211A;">{opp.title}</div>
                                <div style="font-size: 15px; color: #cbd5e1; margin: 3px 0;">Cliente: {opp.customer.full_name if opp.customer else 'N/A'}</div>
                                <div style="font-size: 16px; font-weight: 800; color: #10b981; margin-top: 4px;">${opp.amount_ars:,.0f} ARS</div>
                            </div>
                            """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 3: TAREAS & SEGUIMIENTO
    # -------------------------------------------------------------
    with tab3:
        with get_db_session() as session:
            st.markdown("#### Tareas y Compromisos de Seguimiento")

            col_t1, col_t2 = st.columns([1, 2])
            with col_t1:
                with st.form("form_create_task"):
                    st.markdown("##### Nueva Tarea")
                    task_title = st.text_input("Título de la Tarea", placeholder="Ej: Enviar cotización actualizada")

                    all_custs = search_customers(session=session, user_actor=current_user, limit=100)
                    t_cust_dict = {f"{c.full_name} ({c.phone})": c.id for c in all_custs}
                    t_cust_label = st.selectbox("Cliente", list(t_cust_dict.keys()) if t_cust_dict else ["Sin clientes"])

                    t_type = st.selectbox("Tipo de Tarea", ["WHATSAPP", "LLAMADA", "REUNION", "PRESUPUESTO", "EMAIL"])
                    t_priority = st.selectbox("Prioridad", ["BAJA", "MEDIA", "ALTA", "URGENTE"])
                    t_due = st.date_input("Fecha Límite", datetime.date.today() + datetime.timedelta(days=1))

                    btn_save_task = st.form_submit_button("Crear Tarea", use_container_width=True)
                    if btn_save_task:
                        if not task_title or not task_title.strip():
                            st.error("El título de la tarea es obligatorio.")
                        elif not t_cust_dict:
                            st.error("No hay clientes registrados en el sistema para asignar esta tarea.")
                        else:
                            due_datetime = datetime.datetime.combine(t_due, datetime.time(12, 0))
                            create_task(
                                session=session,
                                customer_id=t_cust_dict[t_cust_label],
                                title=task_title.strip(),
                                due_date=due_datetime,
                                task_type=t_type,
                                priority=t_priority,
                                assigned_user_id=current_user["id"],
                                user_actor=current_user,
                            )
                            session.commit()
                            st.success("Tarea programada.")
                            st.rerun()

            with col_t2:
                pending_tasks = get_pending_tasks(session, user_actor=current_user)
                st.markdown(f"##### Tareas Pendientes ({len(pending_tasks)})")

                if not pending_tasks:
                    st.info("No hay tareas pendientes. Todas las actividades están al día.")
                else:
                    for task in pending_tasks:
                        is_overdue = task.due_date < datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                        badge_color = "#ef4444" if is_overdue or task.priority == "URGENTE" else "#f59e0b" if task.priority == "ALTA" else "#895522"

                        col_tk1, col_tk2 = st.columns([4, 1])
                        with col_tk1:
                            st.markdown(f"""
                            <div style="background: rgba(30, 41, 59, 0.7); border-left: 5px solid {badge_color}; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                                <div style="font-size: 17px; font-weight: 700; color: #2B211A;">{task.title}</div>
                                <div style="font-size: 15px; color: #cbd5e1; margin-top: 4px;">
                                    Cliente: {task.customer.full_name if task.customer else 'N/A'} ({task.customer.phone if task.customer else ''}) |
                                    <b>Tipo:</b> {task.task_type} |
                                    <span style="color: {badge_color}; font-weight: bold;">{'VENCIDA' if is_overdue else 'Vence'}: {task.due_date.strftime('%Y-%m-%d')}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_tk2:
                            if st.button("✓ Listo", key=f"btn_done_{task.id}", use_container_width=True):
                                complete_task(session, task.id, user_actor=current_user)
                                session.commit()
                                st.rerun()

    # -------------------------------------------------------------
    # TAB 4: NUEVO PROSPECTO / CLIENTE MANUAL
    # -------------------------------------------------------------
    with tab4:
        with get_db_session() as session:
            st.markdown("#### Alta Manual de Prospecto / Cliente")
            with st.form("form_new_customer"):
                nc_col1, nc_col2, nc_col3 = st.columns(3)
                with nc_col1:
                    n_phone = st.text_input("Teléfono (con código de país/área)", placeholder="+54911...")
                    n_name = st.text_input("Nombre y Apellido / Contacto", placeholder="Ej: Roberto Gomez")
                with nc_col2:
                    n_email = st.text_input("Email", placeholder="contacto@empresa.com")
                    n_company = st.text_input("Empresa / Razón Social", placeholder="Agropecuaria del Sur S.A.")
                with nc_col3:
                    n_prod = st.selectbox("Línea de Interés", ["Sentek", "Davis", "Jardinería", "Raphael", "GSI", "General"])
                    n_status = st.selectbox("Estado Inicial", ["NUEVO", "CALIFICADO", "EN_SEGUIMIENTO", "COTIZADO"])

                n_notes = st.text_area("Consulta Inicial / Notas")
                btn_create_cust = st.form_submit_button("Guardar en Base de Datos", use_container_width=True)

                if btn_create_cust:
                    if not n_phone or not n_phone.strip():
                        st.error("El número de teléfono es obligatorio.")
                    elif not n_name or not n_name.strip():
                        st.error("El nombre y apellido o contacto es obligatorio.")
                    elif n_email and n_email.strip() and not is_valid_email(n_email.strip()):
                        st.error("El correo electrónico ingresado no tiene un formato válido (ejemplo: contacto@empresa.com).")
                    else:
                        cust, created = create_or_update_customer(
                            session=session,
                            phone=n_phone.strip(),
                            full_name=n_name.strip(),
                            email=n_email.strip() if n_email else None,
                            company=n_company.strip() if n_company else None,
                            product_line=n_prod,
                            status=n_status,
                            notes=n_notes.strip() if n_notes else None,
                            assigned_user_id=current_user["id"],
                            user_actor=current_user,
                        )
                        session.commit()
                        st.success(f"✓ Cliente {'creado' if created else 'actualizado'} exitosamente con ID {cust.id}.")
                        st.rerun()
