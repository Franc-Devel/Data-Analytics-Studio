"""
FAUVOR Analytics - Vista de Administración, Usuarios, Roles, Auditoría y Sincronización (Streamlit)
Disponible para administradores y gerentes corporativos.
"""

import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

from finance_app.db.session import get_db_session
from finance_app.db.models import User, AuditLog, AssignmentRule
from finance_app.db.auth_service import create_user, ROLE_PERMISSIONS
from finance_app.db.audit_service import get_audit_trail, log_audit_event
from finance_app.db.excel_sync import (
    import_leads_excel_to_db,
    import_commercial_excel_to_db,
    export_db_customers_to_dataframe,
)
from finance_app.services.assignment_rules import create_assignment_rule
from finance_app.config import get_config


from finance_app.services.airtable_auth_service import (
    fetch_all_users,
    find_user_by_email,
    create_airtable_user,
    delete_airtable_user,
    admin_reset_user_password,
    admin_update_user_account,
    validate_password_policy,
    is_valid_email,
)
from finance_app.views.auth_view import render_password_requirements_card


def render_admin_view(current_user: dict):
    """Renderiza el panel de control administrativo y auditoría."""
    if current_user.get("role") not in ("admin", "manager"):
        st.error("Acceso denegado: Esta sección requiere privilegios de Administrador o Gerente.")
        return

    st.markdown("## Centro de Administración & Auditoría")
    st.caption("Control centralizado de cuentas Cloud, políticas de acceso RBAC, ciberseguridad y trazabilidad.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Cuentas & Usuarios (Airtable Cloud)",
        "📜 Registro de Auditoría (Audit Log)",
        "🎯 Reglas de Asignación Automática",
        "🔄 Sincronización Excel <-> Base de Datos",
    ])

    # -------------------------------------------------------------
    # TAB 1: GESTIÓN Y CONTROL DE CUENTAS (AIRTABLE CLOUD)
    # -------------------------------------------------------------
    with tab1:
        st.markdown("#### 🛡️ Gestión Centralizada de Cuentas Cloud (Airtable)")
        st.caption("Control de accesos, reseteo de credenciales, roles y estados. Las contraseñas están resguardadas criptográficamente y nunca son visibles.")

        # Obtener lista de usuarios actualizados de Airtable
        cloud_users = fetch_all_users()

        # Métricas de Seguridad
        m_total = len(cloud_users)
        m_admins = sum(1 for u in cloud_users if u.get("rol") == "admin")
        m_2fa = sum(1 for u in cloud_users if u.get("totp_enabled"))
        m_resets = sum(1 for u in cloud_users if u.get("reset_generico"))

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        with c_m1:
            st.metric("Total de Cuentas", m_total)
        with c_m2:
            st.metric("Administradores", m_admins)
        with c_m3:
            st.metric("Cuentas con 2FA Activo", m_2fa)
        with c_m4:
            st.metric("Reseteos Pendientes", m_resets)

        st.write("")

        # Tabla de Cuentas
        if not cloud_users:
            st.info("ℹ️ No hay cuentas registradas en Airtable aún. Utiliza el formulario inferior para dar de alta la primera cuenta.")
        else:
            table_rows = []
            for u in cloud_users:
                role_badge = "🛡️ Admin" if u.get("rol") == "admin" else ("💼 Gerente" if u.get("rol") == "manager" else ("🎯 Closer" if u.get("rol") == "closer" else "👁️ Viewer"))
                status_badge = "🟢 Activo" if u.get("activo") else "🔴 Suspendido"
                totp_badge = "🔐 Activado" if u.get("totp_enabled") else "⏳ Pendiente"
                reset_badge = "⚠️ Sí (Pendiente)" if u.get("reset_generico") else "✓ No"
                table_rows.append({
                    "Nombre": u.get("nombre"),
                    "Correo Electrónico": u.get("email"),
                    "Rol": role_badge,
                    "Estado": status_badge,
                    "2FA": totp_badge,
                    "Reseteo Pendiente": reset_badge,
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

            st.write("")
            st.markdown("---")
            st.markdown("#### ⚙️ Operaciones Administrativas por Cuenta")

            # Selector de Cuenta a gestionar
            user_options = {f"{u.get('nombre')} ({u.get('email')}) — [{u.get('rol').upper()}]": u for u in cloud_users}
            selected_label = st.selectbox("Selecciona una cuenta para administrar:", list(user_options.keys()), key="sb_admin_user_select")
            target_user = user_options[selected_label]

            col_op1, col_op2 = st.columns([1.2, 1])

            # Panel de Modificación de Rol y Estado
            with col_op1:
                st.markdown("##### Configuración de Acceso y Estado")
                with st.form("form_edit_cloud_account"):
                    new_nombre = st.text_input("Nombre Completo:", value=target_user.get("nombre", ""))

                    is_target_current_admin = (target_user.get("email") == current_user.get("email"))
                    is_target_admin = (str(target_user.get("rol")).lower() == "admin")

                    if is_target_admin:
                        st.info("🛡️ **Cuenta del Administrador Único**: Su rol principal no puede ser transferido ni revocado.")
                        new_role = "admin"
                    else:
                        roles_list = ["closer", "viewer", "manager"]
                        current_role_idx = roles_list.index(target_user.get("rol")) if target_user.get("rol") in roles_list else 0
                        new_role = st.selectbox(
                            "Rol de la Cuenta:",
                            roles_list,
                            index=current_role_idx,
                            help="Solamente se permite un Administrador único en el sistema.",
                        )

                    new_active = st.checkbox(
                        "Cuenta Habilitada (Activa)",
                        value=bool(target_user.get("activo")),
                        disabled=is_target_current_admin,
                        help="No puedes suspender tu propia cuenta de administrador." if is_target_current_admin else None,
                    )

                    btn_update_acc = st.form_submit_button("Guardar Cambios de Cuenta", type="primary", use_container_width=True)
                    if btn_update_acc:
                        if not new_nombre or not new_nombre.strip():
                            st.error("El nombre completo es un campo obligatorio.")
                        else:
                            with st.spinner("Guardando en Airtable..."):
                                ok_up, msg_up = admin_update_user_account(
                                    record_id=target_user["record_id"],
                                    fields={
                                        "nombre": new_nombre.strip(),
                                        "rol": new_role,
                                        "activo": new_active,
                                    },
                                    target_user=target_user,
                                    current_admin=current_user,
                                )
                            if ok_up:
                                with get_db_session() as session:
                                    log_audit_event(session, "UPDATE_USER_ACCOUNT", "User", user=current_user.get("username", "admin"), new_data={"target": target_user.get("email"), "rol": new_role, "activo": new_active})
                                    session.commit()
                                st.success(msg_up)
                                st.rerun()
                            else:
                                st.error(msg_up)

            # Panel de Acciones Críticas (Reseteo y Eliminación Protegida)
            with col_op2:
                st.markdown("##### Acciones de Seguridad")

                # 1. Reestablecer Contraseña
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #895522; font-size: 14px;">🔄 Reestablecer Contraseña</div>
                    <div style="font-size: 12.5px; color: #786451; margin-top: 4px;">
                        Restablece la clave a la inicial (<code>Consultora2026!</code>) y activa la marca de reseteo. Al ingresar su mail, el usuario verá el cartel de aviso y deberá definir su clave personal.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"Reestablecer Clave de {target_user.get('nombre')}", use_container_width=True, key=f"btn_reset_{target_user['record_id']}"):
                    with st.spinner("Reestableciendo contraseña en Airtable..."):
                        ok_res, msg_res = admin_reset_user_password(
                            record_id=target_user["record_id"],
                            email=target_user["email"],
                        )
                    if ok_res:
                        with get_db_session() as session:
                            log_audit_event(session, "ADMIN_PASSWORD_RESET", "User", user=current_user.get("username", "admin"), new_data={"target": target_user.get("email")})
                            session.commit()
                        st.success(f"✓ {msg_res}")
                        st.rerun()
                    else:
                        st.error(msg_res)

                st.write("")
                # 2. Eliminación de Cuenta con Protección Estricta
                st.markdown("""
                <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #f87171; font-size: 14px;">🗑️ Eliminación de Cuenta</div>
                    <div style="font-size: 12.5px; color: #fca5a5; margin-top: 4px;">
                        <b>Políticas de Seguridad:</b> Las cuentas con rol Administrador están protegidas y no pueden eliminarse.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                is_admin_role = (target_user.get("rol") == "admin")
                if is_admin_role:
                    st.warning("🛡️ **Cuenta Protegida**: Los usuarios con rol Administrador no pueden ser eliminados del sistema.")
                else:
                    confirm_del = st.checkbox(f"Confirmo eliminar definitivamente a {target_user.get('email')}", key=f"chk_del_{target_user['record_id']}")
                    if st.button("Eliminar Cuenta Definitivamente", type="secondary", disabled=not confirm_del, use_container_width=True, key=f"btn_del_{target_user['record_id']}"):
                        with st.spinner("Eliminando cuenta en Airtable..."):
                            ok_del, msg_del = delete_airtable_user(
                                record_id=target_user["record_id"],
                                target_user=target_user,
                                current_admin=current_user,
                            )
                        if ok_del:
                            with get_db_session() as session:
                                log_audit_event(session, "DELETE_USER", "User", user=current_user.get("username", "admin"), new_data={"deleted_user": target_user.get("email")})
                                session.commit()
                            st.success(msg_del)
                            st.rerun()
                        else:
                            st.error(msg_del)

        # Formulario para Crear Nueva Cuenta Cloud
        st.write("")
        with st.expander("➕ Dar de Alta Nueva Cuenta Cloud en Airtable", expanded=False):
            with st.form("form_create_cloud_user"):
                nu_col1, nu_col2 = st.columns(2)
                with nu_col1:
                    new_cl_name = st.text_input("Nombre Completo:", placeholder="ej: Lucía Fernández")
                    new_cl_email = st.text_input("Correo Electrónico:", placeholder="lucia@consultora.com").strip().lower()
                with nu_col2:
                    new_cl_role = st.selectbox("Rol Asignado:", ["closer", "viewer", "manager"], help="El rol Administrador es único y exclusivo del propietario del sistema.")
                    use_generic = st.checkbox("Asignar contraseña genérica inicial (Consultora2026!)", value=True)

                new_cl_pwd = ""
                req_ok_new = True
                if not use_generic:
                    new_cl_pwd = st.text_input("Contraseña Personal:", type="password", placeholder="••••••••••••")
                    req_ok_new = render_password_requirements_card(new_cl_pwd)

                submit_cloud_user = st.form_submit_button("Crear Cuenta Cloud", type="primary", use_container_width=True)
                if submit_cloud_user:
                    if not new_cl_name or not new_cl_name.strip():
                        st.error("El nombre completo es un campo obligatorio.")
                    elif not new_cl_email:
                        st.error("El correo electrónico es un campo obligatorio.")
                    elif not is_valid_email(new_cl_email):
                        st.error(f"El correo electrónico '{new_cl_email}' no es válido. Debe tener una estructura válida (ejemplo: usuario@empresa.com).")
                    elif not use_generic and not new_cl_pwd:
                        st.error("La contraseña es obligatoria si no utiliza la clave genérica inicial.")
                    elif not use_generic and not req_ok_new:
                        st.error("La contraseña no cumple con todos los requisitos de seguridad obligatorios.")
                    else:
                        final_pwd = "Consultora2026!" if use_generic else new_cl_pwd
                        with st.spinner("Registrando cuenta en Airtable..."):
                            ok_c, msg_c, u_data = create_airtable_user(
                                email=new_cl_email,
                                nombre=new_cl_name,
                                password=final_pwd,
                                rol=new_cl_role,
                                reset_generico=use_generic,
                            )
                        if ok_c:
                            with get_db_session() as session:
                                log_audit_event(session, "CREATE_USER", "User", user=current_user.get("username", "admin"), new_data={"email": new_cl_email, "rol": new_cl_role})
                                session.commit()
                            st.success(f"✓ Cuenta '{new_cl_email}' creada exitosamente en Airtable.")
                            st.rerun()
                        else:
                            st.error(msg_c)


    # -------------------------------------------------------------
    # TAB 2: AUDITORÍA CORPORATIVA
    # -------------------------------------------------------------
    with tab2:
        with get_db_session() as session:
            st.markdown("#### Registro de Auditoría Inmutable (Hash Chaining)")

            # Verificación de Integridad Criptográfica
            from finance_app.db.audit_service import verify_audit_integrity
            col_v1, col_v2 = st.columns([3, 1])
            with col_v1:
                st.caption("Cada registro está firmado criptográficamente con SHA-256 y encadenado al bloque anterior para impedir manipulaciones en BD.")
            with col_v2:
                if st.button("Verificar Integridad", use_container_width=True):
                    is_valid, count, msg = verify_audit_integrity(session)
                    if is_valid:
                        st.success(msg)
                    else:
                        st.error(f"ALERTA DE SEGURIDAD: {msg}")

            f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
            with f_col1:
                filter_entity = st.selectbox("Filtrar por Entidad", ["Todas", "Customer", "Opportunity", "Task", "User", "Config"])
            with f_col2:
                filter_action = st.selectbox("Filtrar por Acción", ["Todas", "LOGIN_SUCCESS", "LOGIN_FAILED", "ACCOUNT_LOCKED", "CREATE", "UPDATE", "DELETE", "IMPORT", "EXPORT", "ANONYMIZE_DATA_SUBJECT"])

            audit_logs = get_audit_trail(
                session=session,
                entity_type=filter_entity if filter_entity != "Todas" else None,
                action=filter_action if filter_action != "Todas" else None,
                limit=100,
            )

            if not audit_logs:
                st.info("No se encontraron registros de auditoría.")
            else:
                audit_records = []
                for a in audit_logs:
                    audit_records.append({
                        "Fecha / Hora": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "Usuario": a.username,
                        "Acción": a.action,
                        "Entidad": a.entity_type,
                        "ID Entidad": a.entity_id or "-",
                        "Datos Previos": (a.old_data_json[:35] + "...") if a.old_data_json and len(a.old_data_json) > 35 else (a.old_data_json or "-"),
                        "Datos Nuevos": (a.new_data_json[:35] + "...") if a.new_data_json and len(a.new_data_json) > 35 else (a.new_data_json or "-"),
                        "SHA-256 Hash": (a.entry_hash[:12] + "...") if a.entry_hash else "N/A",
                    })
                st.dataframe(pd.DataFrame(audit_records), use_container_width=True, hide_index=True)


    # -------------------------------------------------------------
    # TAB 3: REGLAS DE ASIGNACIÓN AUTOMÁTICA
    # -------------------------------------------------------------
    with tab3:
        with get_db_session() as session:
            st.markdown("#### Reglas de Distribución de Leads")
            rules = session.query(AssignmentRule).order_by(AssignmentRule.priority_order.asc()).all()

            rule_data = []
            for r in rules:
                rule_data.append({
                    "Prioridad": r.priority_order,
                    "Nombre": r.name,
                    "Producto": r.product_line or "Cualquiera",
                    "Región / Prov": r.province_or_region or "Cualquiera",
                    "Score Mín": r.min_lead_score,
                    "Closer Asignado": r.assigned_user.full_name if r.assigned_user else "N/A",
                    "Activa": "Sí" if r.is_active else "No",
                })
            st.dataframe(pd.DataFrame(rule_data), use_container_width=True, hide_index=True)

            with st.expander("Crear Nueva Regla de Asignación", expanded=False):
                with st.form("form_create_rule"):
                    r_col1, r_col2 = st.columns(2)
                    with r_col1:
                        r_name = st.text_input("Nombre de la Regla", placeholder="Ej: Leads Agro Norte -> Sergio")
                        r_prod = st.selectbox("Línea de Producto", ["Cualquiera", "Sentek", "Davis", "Jardinería", "Raphael", "GSI"])
                        r_geo = st.text_input("Provincia o Región (Opcional)", placeholder="Ej: Córdoba, Pampeana...")
                    with r_col2:
                        r_score = st.slider("Score Mínimo Requerido", 0, 100, 0)
                        r_prio = st.number_input("Orden de Prioridad", min_value=1, value=len(rules) + 1)

                        closers = session.query(User).filter(User.role.in_(["closer", "admin", "manager"])).all()
                        closer_map = {c.full_name: c.id for c in closers}
                        r_closer_label = st.selectbox("Closer Destino", list(closer_map.keys()))

                    submit_rule = st.form_submit_button("Guardar Regla", use_container_width=True)
                    if submit_rule:
                        if not r_name or not r_name.strip():
                            st.error("El nombre de la regla es obligatorio.")
                        elif not closer_map:
                            st.error("No hay usuarios de tipo closer, admin o manager disponibles para asignar la regla.")
                        else:
                            create_assignment_rule(
                                session=session,
                                name=r_name.strip(),
                                assigned_user_id=closer_map[r_closer_label],
                                product_line=r_prod if r_prod != "Cualquiera" else None,
                                province_or_region=r_geo.strip() if r_geo else None,
                                min_lead_score=r_score,
                                priority_order=r_prio,
                            )
                            log_audit_event(session, "CREATE_RULE", "AssignmentRule", user=current_user["username"], new_data={"rule": r_name.strip()})
                            session.commit()
                            st.success(f"✓ Regla '{r_name.strip()}' creada correctamente.")
                            st.rerun()

    # -------------------------------------------------------------
    # TAB 4: SINCRONIZACIÓN EXCEL <-> BASE DE DATOS
    # -------------------------------------------------------------
    with tab4:
        with get_db_session() as session:
            st.markdown("#### Migración y Sincronización Bidireccional")
            cfg = get_config()

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; padding: 18px 20px;">
                    <h5 style="color: #895522; margin-bottom: 8px; font-size: 20px;">Importar desde Archivos Excel a BD</h5>
                    <p style="font-size: 16.5px; color: #2B211A; line-height: 1.55;">Carga masivamente los datos de <code>Leeds orden.xlsx</code> y <code>Comercial.xlsx</code> hacia las tablas SQL.</p>
                </div>
                """, unsafe_allow_html=True)

                if st.button("Iniciar Ingesta Completa Excel -> SQL", use_container_width=True):
                    with st.spinner("Importando bases de datos..."):
                        leads_path = cfg.resolve_leads_path()
                        comm_path = cfg.resolve_commercial_path()

                        created, updated = import_leads_excel_to_db(session, leads_path, user_actor=current_user["username"])
                        opps_count = import_commercial_excel_to_db(session, comm_path, user_actor=current_user["username"])
                        session.commit()
                        st.success(f"✓ Ingesta completada: {created} leads creados, {updated} actualizados, {opps_count} oportunidades registradas.")
                        st.rerun()

            with col_s2:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(71,102,79,0.25); border-radius: 12px; padding: 18px 20px;">
                    <h5 style="color: #47664F; margin-bottom: 8px; font-size: 20px;">Exportar Base de Datos a Excel</h5>
                    <p style="font-size: 16.5px; color: #2B211A; line-height: 1.55;">Descarga la base consolidada de clientes con scoring y closer asignado en formato Excel.</p>
                </div>
                """, unsafe_allow_html=True)

                df_export = export_db_customers_to_dataframe(session)
                if not df_export.empty:
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_export.to_excel(writer, sheet_name="Clientes_Consolidados", index=False)
                    st.download_button(
                        label=f"Descargar Clientes SQL ({len(df_export)} registros) en .xlsx",
                        data=output.getvalue(),
                        file_name="nexo_analytics_clientes_crm.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.info("No hay registros en la base de datos para exportar. Ejecute la importación primero.")
