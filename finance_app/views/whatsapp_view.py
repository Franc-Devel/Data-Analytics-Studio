"""
FAUVOR Analytics - Vista de Conexión, Monitoreo y Cola de Mensajería de WhatsApp (Streamlit)
"""

import json
from pathlib import Path
import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

from finance_app.db.session import get_db_session
from finance_app.db.models import WhatsAppQueueMessage
from finance_app.services.whatsapp_queue import enqueue_whatsapp_message, process_next_queue_batch, get_queue_metrics
from finance_app.whatsapp_service import (
    get_whatsapp_gateway_status,
    request_whatsapp_pairing_code,
    reset_whatsapp_session,
    ensure_whatsapp_bridge_running,
    get_whatsapp_history_stats,
    WhatsAppSyncState,
)


def render_whatsapp_view(current_user: dict):
    """Renderiza el monitor de WhatsApp, cola de envíos y vinculación QR."""
    st.markdown("## WhatsApp Automation & Outbound Queue")
    st.caption("Estado del microservicio Node.js/Baileys, monitor de sincronización y despachador de cola con reintentos.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Cola de Mensajería & Reintentos",
        "Conexión del Microservicio & QR",
        "Mensajes Entrantes en Vivo",
        "Copiloto IA (API LLM)",
    ])

    # -------------------------------------------------------------
    # TAB 1: COLA DE MENSAJERÍA SALIENTE
    # -------------------------------------------------------------
    with tab1:
        with get_db_session() as session:
            metrics = get_queue_metrics(session)

            # Tarjetas de Métricas de Cola
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pendientes / Reintentos", metrics["pending"], help="Mensajes en cola esperando despacho")
            c2.metric("Entregados con Éxito", metrics["sent_total"])
            c3.metric("Fallidos Definitivos", metrics["failed_total"])
            c4.metric("Total Histórico", metrics["total"])

            st.divider()

            col_q1, col_q2 = st.columns([2, 1])
            with col_q1:
                st.markdown("##### Mensajes en Cola")
                queue_items = (
                    session.query(WhatsAppQueueMessage)
                    .order_by(WhatsAppQueueMessage.created_at.desc())
                    .limit(25)
                    .all()
                )

                if not queue_items:
                    st.info("La cola de mensajería está vacía.")
                else:
                    q_data = []
                    for q in queue_items:
                        q_data.append({
                            "ID": q.id,
                            "Teléfono": q.phone,
                            "Mensaje": (q.message_text[:35] + "...") if len(q.message_text) > 35 else q.message_text,
                            "Prioridad": q.priority,
                            "Estado": q.status,
                            "Intentos": f"{q.attempts}/{q.max_attempts}",
                            "Creado": q.created_at.strftime("%H:%M:%S") if q.created_at else "-",
                            "Próximo Reintento": q.next_retry_at.strftime("%H:%M:%S") if q.next_retry_at else "-",
                        })
                    st.dataframe(pd.DataFrame(q_data), use_container_width=True, hide_index=True)

                # Botón para procesar lote manualmente
                if st.button("Despachar Lote Pendiente Ahora", use_container_width=True):
                    with st.spinner("Procesando cola de salida..."):
                        sent, failed = process_next_queue_batch(session, batch_size=10, dry_run=False)
                        st.success(f"✓ Procesamiento completado: {sent} enviados, {failed} con error/reintento programado.")
                        st.rerun()

            with col_q2:
                with st.form("form_enqueue"):
                    st.markdown("##### Encolar Mensaje Manual")
                    eq_phone = st.text_input("Número de Destino", placeholder="+54911...")
                    eq_msg = st.text_area("Texto del Mensaje", placeholder="Estimado cliente...", height=100)
                    eq_prio = st.slider("Prioridad (1=Alta, 10=Baja)", 1, 10, 5)
                    submit_eq = st.form_submit_button("Encolar para Envío", use_container_width=True)

                    if submit_eq:
                        if not eq_phone or not eq_phone.strip():
                            st.error("El número de destino es obligatorio.")
                        elif not eq_msg or not eq_msg.strip():
                            st.error("El texto del mensaje es obligatorio.")
                        else:
                            enqueue_whatsapp_message(
                                session=session,
                                phone=eq_phone.strip(),
                                message_text=eq_msg.strip(),
                                priority=eq_prio,
                            )
                            session.commit()
                            st.success("Mensaje agregado a la cola de salida.")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 2: CONEXIÓN & QR / CÓDIGO DE 8 DÍGITOS
    # -------------------------------------------------------------
    with tab2:
        status_info = get_whatsapp_gateway_status()
        is_connected = status_info.get("connected", False) or status_info.get("status") == "CONECTADO"

        c_st1, c_st2 = st.columns([1.2, 1])
        with c_st1:
            if is_connected:
                st.success("Puente de WhatsApp Conectado y Operativo")
                user_phone = status_info.get("phone", status_info.get("user_phone", "No disponible"))
                st.markdown(f"**Teléfono Vinculado:** `+{user_phone}`")
            else:
                st.warning("Sesión de WhatsApp no vinculada o esperando escaneo QR.")

            st.markdown(f"**Proveedor:** `{status_info.get('provider', 'WhatsApp Web Multi-Device (Bridge)')}`")
            st.markdown(f"**Mensaje de Estado:** {status_info.get('message', '')}")

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("Refrescar Estado / QR", use_container_width=True):
                    ensure_whatsapp_bridge_running()
                    st.rerun()
            with col_b2:
                if st.button("Reiniciar Sesión", type="secondary", use_container_width=True):
                    reset_whatsapp_session()
                    st.success("Sesión reiniciada. Escanee el nuevo QR.")
                    st.rerun()

        with c_st2:
            qr_data = status_info.get("qr_png")
            if qr_data:
                st.image(qr_data, caption="Escanee con WhatsApp Business en su celular", width=220)
            elif is_connected:
                st.info("Dispositivo vinculado. No se requiere código QR.")
            else:
                st.caption("Iniciando servicio de WhatsApp... Presione 'Refrescar Estado' en unos segundos.")

        st.divider()

        # Vinculación alternativa por código de 8 dígitos
        with st.expander("Opción Alternativa: Vincular con Código de 8 Dígitos (Sin Cámara)", expanded=not is_connected):
            col_p1, col_p2 = st.columns([1.2, 1.8])
            with col_p1:
                input_phone = st.text_input(
                    "Número con código de país (ej: 5493512345678)",
                    value="549351",
                    key="pair_phone_input",
                )
                if st.button("Generar Código de 8 Dígitos", type="primary", use_container_width=True):
                    with st.spinner("Solicitando código a WhatsApp..."):
                        pair_res = request_whatsapp_pairing_code(input_phone)
                        if pair_res.get("ok"):
                            st.session_state["last_pairing_code"] = pair_res.get("pairing_code")
                            st.success(f"✓ Código generado: **{pair_res.get('pairing_code')}**")
                        else:
                            st.error(f"Error: {pair_res.get('error')}")

            with col_p2:
                if st.session_state.get("last_pairing_code"):
                    c_str = st.session_state["last_pairing_code"]
                    formatted = f"{c_str[:4]} - {c_str[4:]}" if len(c_str) == 8 else c_str
                    st.markdown(f"""
                    <div style="background-color: #E9EFE7; border: 2px solid #47664F; border-radius: 12px; padding: 18px; text-align: center;">
                        <div style="font-size: 15px; color: #a7f3d0; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px;">Tu Código de Vinculación</div>
                        <div style="font-size: 36px; color: #2B211A; font-weight: 800; letter-spacing: 4px; margin: 8px 0;">{formatted}</div>
                        <div style="font-size: 15.5px; color: #6ee7b7;">Introduce este código en Dispositivos Vinculados en tu celular</div>
                    </div>
                    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 3: MENSAJES ENTRANTES EN VIVO
    # -------------------------------------------------------------
    with tab3:
        wa_state = WhatsAppSyncState()
        h_stats = get_whatsapp_history_stats()

        c_sync1, c_sync2, c_sync3 = st.columns(3)
        c_sync1.metric("Mensajes en Memoria", f"{h_stats.get('total_messages', 0):,}")
        c_sync2.metric("Contactos Únicos", f"{h_stats.get('unique_contacts', len(wa_state.processed_phones)):,}")
        c_sync3.metric("Leads Sincronizados", f"{getattr(wa_state, 'total_synced_leads', len(wa_state.processed_ids)):,}")

        st.caption(f"Última Sincronización Registrada: `{wa_state.last_sync_iso[:19].replace('T', ' ')}`")
        st.divider()

        inbox_file = Path("whatsapp_inbox/live_incoming_messages.json")
        if inbox_file.exists():
            try:
                with open(inbox_file, "r", encoding="utf-8") as f:
                    live_msgs = json.load(f)
                if live_msgs and isinstance(live_msgs, list):
                    st.markdown("##### Últimos Mensajes Recibidos en Vivo:")
                    display_records = []
                    for m in reversed(live_msgs[-30:]):
                        display_records.append({
                            "Teléfono": m.get("phone", "-"),
                            "Contacto": m.get("name", m.get("push_name", "Cliente")),
                            "Mensaje": m.get("text", m.get("message", "-")),
                            "Tipo": "Saliente (Empresa)" if m.get("is_from_me") else "Entrante (Cliente)",
                            "Fecha / Hora": str(m.get("timestamp", ""))[:19].replace("T", " "),
                        })
                    st.dataframe(pd.DataFrame(display_records), use_container_width=True, hide_index=True)

                    st.markdown("##### 🤖 Análisis Instantáneo con Copiloto IA")
                    msg_options = [
                        f"{m.get('name', 'Contacto')} ({m.get('phone', '-')}) - {str(m.get('text', m.get('message', '')))[:60]}..."
                        for m in reversed(live_msgs[-30:])
                    ]
                    selected_msg_label = st.selectbox("Seleccionar mensaje de la bandeja para auditar:", msg_options, key="live_msg_select")
                    if st.button("Interpretar con Copiloto IA", type="secondary", key="btn_audit_live_msg"):
                        idx = msg_options.index(selected_msg_label)
                        target_msg = list(reversed(live_msgs[-30:]))[idx]
                        from finance_app.services.ai_service import analyze_whatsapp_message
                        with st.spinner("Analizando requerimiento y procedencia con IA..."):
                            an = analyze_whatsapp_message(
                                text=target_msg.get("text", target_msg.get("message", "")),
                                sender_name=target_msg.get("name", ""),
                                sender_phone=target_msg.get("phone", ""),
                            )
                        c_a1, c_a2, c_a3, c_a4 = st.columns(4)
                        c_a1.metric("Línea Producto", an.product_line)
                        c_a2.metric("Intención", an.intent)
                        c_a3.metric("Temperatura", an.temperature)
                        c_a4.metric("Closer Sugerido", an.suggested_closer or "Sin asignar")
                        if an.missing_info:
                            for alert in an.missing_info:
                                st.warning(alert)
                        st.markdown(f"""
                        <div style="background: #FFFAF2; border: 1px solid #D6C0A3; border-radius: 8px; padding: 12px 16px; margin: 8px 0;">
                            <p style="margin: 0 0 4px 0;"><b>Qué está pidiendo:</b> {an.what_is_requesting}</p>
                            <p style="margin: 0 0 4px 0;"><b>Procedencia Geográfica:</b> {an.origin_location}</p>
                            <p style="margin: 0;"><b>Derivación Comercial:</b> <span style="color: #47664F;">{an.derivation_summary}</span></p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No hay mensajes nuevos registrados en la bandeja en vivo.")
            except Exception:
                st.info("Aún no se han registrado mensajes en tiempo real.")
        else:
            st.info("El receptor escucha continuamente a través del puente de WhatsApp y actualiza la ficha de los prospectos en tiempo real.")

    # -------------------------------------------------------------
    # TAB 4: RELEVAMIENTO IA (API LLM COEQUIPER)
    # -------------------------------------------------------------
    with tab4:
        from finance_app.services.ai_service import (
            get_ai_status,
            is_ai_available,
            analyze_whatsapp_message,
        )

        st.markdown("#### Copiloto IA · Relevamiento y Derivación de Mensajes (API LLM)")
        st.caption("Interpretación económica y eficiente en tokens: qué pide el cliente, de dónde viene, alertas de ubicación no informada y derivación automática a closers.")

        status = get_ai_status(force_refresh=True)
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Estado API LLM", "Operativo" if status.get("available") else "Sin API Key (Fallback Activo)")
        col_s2.metric("Modelo LLM", status.get("current_model", "gpt-4o-mini"))
        col_s3.metric("Proveedor", "API OpenAI / Compatible")
        col_s4.metric("Consumo Tokens", "Optimizado (Ultra Bajo)")

        if not status.get("available"):
            st.info("💡 Modo Contingencia Heurístico activo. Para habilitar la inferencia cognitiva con IA, defina `OPENAI_API_KEY` en su archivo `.env` (compatible con OpenAI, OpenRouter, Groq, DeepSeek).")

        st.divider()

        st.markdown("##### Probar Relevamiento e Interpretación en Vivo")
        col_in1, col_in2 = st.columns([2, 1])

        with col_in1:
            sample_text = (
                "Hola buenas tardes, soy Esteban de Río Cuarto. Necesitamos cotización urgente "
                "de una estación meteorológica Davis Vantage Pro 2 con telemetría para monitorear el lote. "
                "¿Tienen stock para entrega inmediata? Nos preocupa la demora del flete. Gracias."
            )
            test_msg = st.text_area("Texto del Mensaje entrante:", value=sample_text, height=110)
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                t_sender = st.text_input("Nombre Remitente (Opcional):", value="Esteban")
            with col_t2:
                t_phone = st.text_input("Teléfono Remitente (Opcional):", value="+54 9 358 123-4567")

            btn_analyze = st.button("Interpretar Mensaje con IA", type="primary", use_container_width=True)

        with col_in2:
            st.markdown("###### Capacidades del Coequiper IA")
            st.markdown("""
            - **Qué pide el cliente:** Síntesis precisa del requerimiento y productos de interés.
            - **Procedencia Geográfica:** Localidad y provincia detectadas.
            - **Control de Faltantes:** Alerta explícita: *'Avisar: cliente no informó lugar'*.
            - **Derivación Directa:** Sugerencia del closer adecuado (Jony, Luisa, Sergio/Alon).
            """)

        if btn_analyze and test_msg:
            with st.spinner("Interpretando mensaje con IA..."):
                analysis = analyze_whatsapp_message(
                    text=test_msg,
                    sender_name=t_sender,
                    sender_phone=t_phone,
                )

            st.success(f"✓ Relevamiento completado ({'IA API (' + status.get('current_model', 'LLM') + ')' if analysis.is_ai_generated else 'Motor de Contingencia Heurístico'})")

            c_res1, c_res2, c_res3, c_res4 = st.columns(4)
            c_res1.metric("Línea Producto", analysis.product_line)
            c_res2.metric("Intención", analysis.intent)
            c_res3.metric("Temperatura", analysis.temperature)
            c_res4.metric("Closer Sugerido", analysis.suggested_closer or "Sin asignar")

            # Alertas si falta información clave (ej: lugar no informado)
            if analysis.missing_info:
                for alert in analysis.missing_info:
                    st.warning(f"{alert}")

            st.markdown(f"""
            <div style="background: #FFFAF2; border: 1px solid #D6C0A3; border-radius: 10px; padding: 14px 18px; margin: 12px 0;">
                <p style="margin: 0 0 6px 0; font-size: 15px; color: #786451;"><b>Qué está pidiendo:</b> <span style="color: #2B211A; font-weight: 600;">{analysis.what_is_requesting}</span></p>
                <p style="margin: 0 0 6px 0; font-size: 15px; color: #786451;"><b>Procedencia / Ubicación:</b> <span style="color: #895522; font-weight: 600;">{analysis.origin_location}</span></p>
                <p style="margin: 0; font-size: 15px; color: #786451;"><b>Derivación Comercial:</b> <span style="color: #47664F; font-weight: 600;">{analysis.derivation_summary}</span></p>
            </div>
            """, unsafe_allow_html=True)

            col_det1, col_det2 = st.columns(2)
            with col_det1:
                st.markdown(f"**Objeciones Detectadas:** `{analysis.objections or 'Ninguna evidente'}`")
                st.markdown(f"**Nivel de Urgencia:** `{analysis.urgency}`")
            with col_det2:
                st.markdown(f"**Resumen Ejecutivo:**\n> {analysis.executive_summary}")
                st.markdown(f"**Acción Recomendada:**\n> {analysis.recommended_action}")

