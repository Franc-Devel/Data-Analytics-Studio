import time
from typing import Dict, Optional, Tuple
import streamlit as st
import streamlit.components.v1 as components

from finance_app.config import get_config
from finance_app.services.airtable_auth_service import (
    authenticate_user_with_airtable,
    fetch_all_users,
    find_user_by_email,
    create_airtable_user,
    activate_user_2fa,
    reset_password_via_2fa,
    generate_totp_secret,
    get_totp_uri,
    generate_qr_code_image_bytes,
    verify_totp_code,
    decrypt_field,
    check_login_rate_limit,
    record_failed_login,
    clear_failed_logins,
    create_encrypted_client_session_token,
    verify_encrypted_client_session_token,
    is_valid_email,
    validate_password_policy,
    validate_registration_fields,
)


def check_password_criteria(pwd: str) -> Dict[str, bool]:
    """Evalúa los 5 requisitos de seguridad de contraseña idéntico a Login.jsx."""
    return {
        "len": 6 <= len(pwd) <= 20,
        "lower": any(c.islower() for c in pwd),
        "upper": any(c.isupper() for c in pwd),
        "digit": any(c.isdigit() for c in pwd),
        "special": any(c in "!@#$%^&*()_+-=[]{};':\"\\|,.<>?/~`" for c in pwd),
    }


def render_password_requirements_card(pwd: str) -> bool:
    """
    Renderiza la tarjeta visual de requisitos de contraseña idéntica a Login.jsx:
    Se muestra únicamente cuando se tipea en la contraseña (form.password.length > 0)
    y valida dinámicamente los 5 requisitos con tildes verdes.
    """
    crit = check_password_criteria(pwd)

    def _row(label: str, ok: bool, rule_cls: str) -> str:
        color = "#10b981" if ok else "#94a3b8"
        if ok:
            icon = """<span style="display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;background:#10b981;border-radius:50%;color:#052e16;font-size:11px;font-weight:900;margin-right:8px;line-height:1;">✓</span>"""
        else:
            icon = """<span style="display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border:1.5px solid #64748b;border-radius:50%;color:transparent;font-size:10px;margin-right:8px;"></span>"""
        return f'<div class="{rule_cls}" style="font-size: 13px; color: {color}; margin-bottom: 4px; display: flex; align-items: center;">{icon} {label}</div>'

    html = f"""
    <div id="pwd-requirements-box" style="background: rgba(0, 0, 0, 0.55); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 8px; padding: 12px 16px; margin: 10px 0 14px 0; {'display: block;' if len(pwd) > 0 else 'display: none;'}">
        <div style="font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 8px;">Requisitos de seguridad de la contraseña:</div>
        <div style="display: flex; flex-direction: column; gap: 3px;">
            {_row("Entre 6 y 20 caracteres", crit["len"], "pwd-rule-len")}
            {_row("Al menos una letra minúscula (a-z)", crit["lower"], "pwd-rule-lower")}
            {_row("Al menos una letra mayúscula (A-Z)", crit["upper"], "pwd-rule-upper")}
            {_row("Al menos un número (0-9)", crit["digit"], "pwd-rule-digit")}
            {_row("Al menos un caracter especial (!, @, #, $, etc.)", crit["special"], "pwd-rule-special")}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    # Inyección de script para escucha reactiva inmediata en cada pulsación de tecla
    components.html("""
    <script>
    (function() {
        function watchPasswords() {
            try {
                const doc = window.parent.document;
                if (!doc) return;
                const pwdInput = doc.querySelector('input[aria-label*="Contraseña *"], input[placeholder*="Contraseña"]');
                if (!pwdInput) return;
                if (pwdInput.dataset.liveWatch) return;
                pwdInput.dataset.liveWatch = "true";
                const input = pwdInput;
                    
                    const updateLiveChecks = () => {
                        const val = input.value || '';
                        const isLen = val.length >= 6 && val.length <= 20;
                        const isLower = /[a-z]/.test(val);
                        const isUpper = /[A-Z]/.test(val);
                        const isDigit = /[0-9]/.test(val);
                        const isSpecial = /[!@#$%^&*()_+\\-=\\[\\]{};':"\\\\|,.<>?/~`]/.test(val);

                        const box = doc.getElementById('pwd-requirements-box');
                        if (box) {
                            box.style.display = val.length > 0 ? 'block' : 'none';
                        }

                        const rows = [
                            { cls: 'pwd-rule-len', ok: isLen, text: 'Entre 6 y 20 caracteres' },
                            { cls: 'pwd-rule-lower', ok: isLower, text: 'Al menos una letra minúscula (a-z)' },
                            { cls: 'pwd-rule-upper', ok: isUpper, text: 'Al menos una letra mayúscula (A-Z)' },
                            { cls: 'pwd-rule-digit', ok: isDigit, text: 'Al menos un número (0-9)' },
                            { cls: 'pwd-rule-special', ok: isSpecial, text: 'Al menos un caracter especial (!, @, #, $, etc.)' }
                        ];

                        rows.forEach(r => {
                            const elements = doc.querySelectorAll('.' + r.cls);
                            elements.forEach(el => {
                                const color = r.ok ? '#10b981' : '#94a3b8';
                                const icon = r.ok 
                                    ? '<span style="display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;background:#10b981;border-radius:50%;color:#052e16;font-size:11px;font-weight:900;margin-right:8px;line-height:1;">✓</span>'
                                    : '<span style="display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border:1.5px solid #64748b;border-radius:50%;color:transparent;font-size:10px;margin-right:8px;"></span>';
                                el.innerHTML = icon + ' ' + r.text;
                                el.style.color = color;
                            });
                        });
                    };

                    input.addEventListener('input', updateLiveChecks);
                    input.addEventListener('keyup', updateLiveChecks);
                    input.addEventListener('change', updateLiveChecks);
            } catch(e) {}
        }
        setInterval(watchPasswords, 200);
        watchPasswords();
    })();
    </script>
    """, height=0, width=0)

    return all(crit.values())


def _inject_progressive_form_guard():
    """Inyecta un guardián JS en el navegador para forzar required, minlength, maxlength y bloqueo progresivo idéntico a Login.jsx."""
    js = r"""
    <script>
    (function() {
        function enforceHtml5Attributes(doc) {
            // Aplicar required, minlength, maxlength y type="email" a todos los inputs relevantes
            const allInputs = doc.querySelectorAll('input');
            allInputs.forEach(inp => {
                const ph = (inp.placeholder || '').toLowerCase();
                const lbl = (inp.getAttribute('aria-label') || '').toLowerCase();
                if (ph.includes('email') || lbl.includes('correo') || lbl.includes('email')) {
                    inp.setAttribute('type', 'email');
                    inp.setAttribute('required', 'required');
                    inp.setAttribute('maxlength', '60');
                }
                if (lbl.includes('nombre') || ph.includes('nombre') || ph.includes('alias')) {
                    inp.setAttribute('required', 'required');
                    inp.setAttribute('minlength', '3');
                    inp.setAttribute('maxlength', '40');
                }
                if (inp.type === 'password' || ph.includes('contraseña') || lbl.includes('contraseña')) {
                    inp.setAttribute('required', 'required');
                    inp.setAttribute('minlength', '6');
                    inp.setAttribute('maxlength', '20');
                }
            });
        }

        function findRegisterElements(doc) {
            const nameIn = doc.querySelector('input[aria-label*="Nombre o alias"]');
            if (!nameIn) return null;

            let container = nameIn.closest('[role="tabpanel"], div[data-baseweb="tab-panel"], div[data-testid="stTabContent"]');
            if (!container) {
                let parent = nameIn.parentElement;
                while (parent && parent !== doc.body) {
                    if (parent.querySelectorAll('input').length >= 3) {
                        container = parent;
                        break;
                    }
                    parent = parent.parentElement;
                }
            }
            if (!container) return null;

            const emailIn = container.querySelector('input[aria-label*="Email"]');
            const pwdIn = container.querySelector('input[aria-label*="Contraseña *"], input[placeholder*="Contraseña"]');
            const pwdRepIn = container.querySelector('input[aria-label*="Repetir contraseña"], input[placeholder*="Repetir"]');

            return { nameIn, emailIn, pwdIn, pwdRepIn, container };
        }

        function checkProgressiveSteps() {
            try {
                const doc = window.parent.document;
                if (!doc) return;

                enforceHtml5Attributes(doc);

                const els = findRegisterElements(doc);
                if (!els || !els.nameIn || !els.emailIn) return;

                const { nameIn, emailIn, pwdIn, pwdRepIn } = els;

                // Forzar atributos HTML5 de required y type email idénticos a Login.jsx
                nameIn.setAttribute('required', 'required');
                nameIn.setAttribute('minlength', '3');
                nameIn.setAttribute('maxlength', '40');

                emailIn.setAttribute('required', 'required');
                emailIn.setAttribute('type', 'email');
                emailIn.setAttribute('maxlength', '60');

                if (pwdIn) {
                    pwdIn.setAttribute('required', 'required');
                    pwdIn.setAttribute('minlength', '6');
                    pwdIn.setAttribute('maxlength', '20');
                }
                if (pwdRepIn) {
                    pwdRepIn.setAttribute('required', 'required');
                    pwdRepIn.setAttribute('minlength', '6');
                    pwdRepIn.setAttribute('maxlength', '20');
                }

                if (!emailIn.dataset.guardEvt) {
                    emailIn.dataset.guardEvt = "true";
                    emailIn.addEventListener('input', checkProgressiveSteps);
                    emailIn.addEventListener('keyup', checkProgressiveSteps);
                    emailIn.addEventListener('change', checkProgressiveSteps);
                }
                if (!nameIn.dataset.guardEvt) {
                    nameIn.dataset.guardEvt = "true";
                    nameIn.addEventListener('input', checkProgressiveSteps);
                    nameIn.addEventListener('keyup', checkProgressiveSteps);
                    nameIn.addEventListener('change', checkProgressiveSteps);
                }
                if (pwdIn && !pwdIn.dataset.guardEvt) {
                    pwdIn.dataset.guardEvt = "true";
                    pwdIn.addEventListener('input', checkProgressiveSteps);
                    pwdIn.addEventListener('keyup', checkProgressiveSteps);
                    pwdIn.addEventListener('change', checkProgressiveSteps);
                }
                if (pwdRepIn && !pwdRepIn.dataset.guardEvt) {
                    pwdRepIn.dataset.guardEvt = "true";
                    pwdRepIn.addEventListener('input', checkProgressiveSteps);
                    pwdRepIn.addEventListener('keyup', checkProgressiveSteps);
                    pwdRepIn.addEventListener('change', checkProgressiveSteps);
                }

                const nameVal = (nameIn.value || '').trim();
                const isNameOk = nameVal.length >= 3 && nameVal.length <= 40;

                if (!isNameOk) {
                    emailIn.disabled = true;
                    emailIn.style.opacity = '0.5';
                    emailIn.style.cursor = 'not-allowed';
                    emailIn.style.pointerEvents = 'none';

                    if (pwdIn) {
                        pwdIn.disabled = true;
                        pwdIn.style.opacity = '0.5';
                        pwdIn.style.cursor = 'not-allowed';
                        pwdIn.style.pointerEvents = 'none';
                    }
                    if (pwdRepIn) {
                        pwdRepIn.disabled = true;
                        pwdRepIn.style.opacity = '0.5';
                        pwdRepIn.style.cursor = 'not-allowed';
                        pwdRepIn.style.pointerEvents = 'none';
                    }
                    return;
                }

                // Nombre completo es válido -> habilitar campo de correo
                emailIn.disabled = false;
                emailIn.style.opacity = '1';
                emailIn.style.cursor = 'text';
                emailIn.style.pointerEvents = 'auto';

                const rawEmail = (emailIn.value || '').trim();
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                const parts = rawEmail.split('.');
                const tld = parts[parts.length - 1] || '';
                const isEmailOk = emailRegex.test(rawEmail) && !rawEmail.includes('..') && tld.length >= 2;

                if (!isEmailOk) {
                    // Si el email NO es válido: BLOQUEAR contraseña completamente
                    if (pwdIn) {
                        pwdIn.disabled = true;
                        pwdIn.style.opacity = '0.5';
                        pwdIn.style.cursor = 'not-allowed';
                        pwdIn.style.pointerEvents = 'none';
                    }
                    if (pwdRepIn) {
                        pwdRepIn.disabled = true;
                        pwdRepIn.style.opacity = '0.5';
                        pwdRepIn.style.cursor = 'not-allowed';
                        pwdRepIn.style.pointerEvents = 'none';
                    }
                    if (rawEmail.length > 0) {
                        emailIn.style.borderColor = '#ef4444';
                    } else {
                        emailIn.style.borderColor = '';
                    }
                } else {
                    // Email con formato válido -> DESBLOQUEAR contraseña y repetir contraseña
                    emailIn.style.borderColor = '#10b981';
                    if (pwdIn) {
                        pwdIn.disabled = false;
                        pwdIn.style.opacity = '1';
                        pwdIn.style.cursor = 'text';
                        pwdIn.style.pointerEvents = 'auto';
                    }
                    if (pwdRepIn) {
                        pwdRepIn.disabled = false;
                        pwdRepIn.style.opacity = '1';
                        pwdRepIn.style.cursor = 'text';
                        pwdRepIn.style.pointerEvents = 'auto';
                        if (pwdRepIn.placeholder && pwdRepIn.placeholder.includes('Cumple los requisitos')) {
                            pwdRepIn.placeholder = 'Repetir contraseña (6 a 20 caracteres)';
                        }
                    }

                    // Validación visual inmediata de coincidencia de contraseñas
                    if (pwdIn && pwdRepIn && pwdRepIn.value) {
                        if (pwdIn.value === pwdRepIn.value) {
                            pwdRepIn.style.borderColor = '#10b981';
                        } else {
                            pwdRepIn.style.borderColor = '#ef4444';
                        }
                    } else if (pwdRepIn) {
                        pwdRepIn.style.borderColor = '';
                    }
                }
            } catch (e) {}
        }
        setInterval(checkProgressiveSteps, 120);
        checkProgressiveSteps();
    })();
    </script>
    """
    components.html(js, height=0, width=0)


def _inject_storage_vault_saver(encrypted_token: str):
    """Guarda el token cifrado de sesión militarmente en sessionStorage y localStorage."""
    safe_token = encrypted_token.replace('"', '\\"').replace("'", "\\'")
    js = f"""
    <script>
        (function() {{
            try {{
                const token = "{safe_token}";
                sessionStorage.setItem("__nexo_sec_vault", token);
                localStorage.setItem("__nexo_sec_vault", token);
            }} catch (e) {{
                console.warn("Storage restricted:", e);
            }}
        }})();
    </script>
    """
    components.html(js, height=0)


def _inject_storage_vault_cleaner():
    """Purga completamente cualquier rastro de la bóveda de sesión en el navegador."""
    js = """
    <script>
        (function() {
            try {
                sessionStorage.removeItem("__nexo_sec_vault");
                localStorage.removeItem("__nexo_sec_vault");
            } catch (e) {}
            try {
                if (window.parent && window.parent.sessionStorage) {
                    window.parent.sessionStorage.removeItem("__nexo_sec_vault");
                    window.parent.localStorage.removeItem("__nexo_sec_vault");
                }
            } catch (e) {}
            try {
                const targetWin = (window.parent && window.parent.location) ? window.parent : window;
                if (targetWin.location.search.includes("_st_sec_vault")) {
                    const url = new URL(targetWin.location);
                    url.searchParams.delete("_st_sec_vault");
                    targetWin.history.replaceState({}, targetWin.document.title, url.pathname + (url.search ? url.search : ""));
                }
            } catch (e) {}
        })();
    </script>
    """
    components.html(js, height=0)


def _inject_storage_vault_listener():
    """Detecta si hay una sesión válida en sessionStorage o localStorage al recargar la página (F5)."""
    js = """
    <script>
        (function() {
            try {
                let sToken = null;
                try {
                    if (window.parent && window.parent.sessionStorage) {
                        sToken = window.parent.sessionStorage.getItem("__nexo_sec_vault") || window.parent.localStorage.getItem("__nexo_sec_vault");
                    }
                } catch(e) {}
                if (!sToken) {
                    sToken = sessionStorage.getItem("__nexo_sec_vault") || localStorage.getItem("__nexo_sec_vault");
                }
                const targetWin = (window.parent && window.parent.location) ? window.parent : window;
                if (sToken && !targetWin.location.search.includes("_st_sec_vault")) {
                    const sep = targetWin.location.search ? "&" : "?";
                    targetWin.location.replace(targetWin.location.href + sep + "_st_sec_vault=" + encodeURIComponent(sToken));
                }
            } catch (e) {}
        })();
    </script>
    """
    components.html(js, height=0)


def init_auth_session():
    """Inicializa variables de sesión en Streamlit."""
    cfg = get_config()
    if not cfg.auth_enabled:
        if st.session_state.get("logged_out"):
            return
        if st.session_state.get("current_user") is None:
            st.session_state["current_user"] = {
                "id": "admin-01",
                "username": "juan.perez@consultora.com",
                "full_name": "Juan Pérez",
                "role": "admin",
                "email": "juan.perez@consultora.com",
                "must_change_password": False,
                "token_version": 1,
                "last_activity": time.time(),
            }
        return

    if "current_user" not in st.session_state:
        st.session_state["current_user"] = None
    if "auth_flow_step" not in st.session_state:
        st.session_state["auth_flow_step"] = "LOGIN"


def render_login_form() -> bool:
    """
    Renderiza el portal de autenticación seguro conectado a Airtable con 2FA (Google Authenticator)
    y Bóveda de Almacenamiento Cifrada en Cliente (sessionStorage & localStorage).
    """
    cfg = get_config()
    if not cfg.auth_enabled:
        init_auth_session()
        if st.session_state.get("logged_out"):
            st.info("👋 Has cerrado la sesión correctamente.")
            if st.button("🔑 Volver a Iniciar Sesión", type="primary", use_container_width=True):
                st.session_state["logged_out"] = False
                st.session_state["current_user"] = None
                init_auth_session()
                st.rerun()
            return False
        return True

    init_auth_session()

    current_user = st.session_state.get("current_user")

    # 1. Comprobar timeout de inactividad de sesión (30 minutos)
    if current_user is not None:
        last_act = current_user.get("last_activity", time.time())
        if (time.time() - last_act) > 1800:
            st.session_state["current_user"] = None
            st.session_state["logged_out"] = True
            st.query_params.clear()
            _inject_storage_vault_cleaner()
            st.warning("⏱️ Tu sesión ha expirado por inactividad de 30 minutos. Por favor reingresa.")
            st.rerun()
            return False
        current_user["last_activity"] = time.time()
        return True

    # 2. Restauración automática desde la Bóveda Cifrada de Almacenamiento
    token_in_url = st.query_params.get("_st_sec_vault")
    if token_in_url and not current_user:
        if st.session_state.get("logged_out"):
            st.query_params.clear()
            _inject_storage_vault_cleaner()
        else:
            restored_user = verify_encrypted_client_session_token(token_in_url)
            if restored_user:
                st.session_state["current_user"] = restored_user
                st.session_state["auth_flow_step"] = "LOGIN"
                _inject_storage_vault_saver(token_in_url)
                st.rerun()
                return True
            else:
                # Token alterado o expirado
                st.query_params.clear()
                _inject_storage_vault_cleaner()

    # Si se solicitó cerrar sesión, purgar bóveda local y NO activar el listener automático
    if st.session_state.get("logged_out"):
        _inject_storage_vault_cleaner()
    else:
        # Si no hay token en URL, activar listener del navegador para leer sessionStorage / localStorage
        _inject_storage_vault_listener()


    step = st.session_state.get("auth_flow_step", "LOGIN")

    col_l1, col_l2, col_l3 = st.columns([1, 2.2, 1])
    with col_l2:
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.90); border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 12px; padding: 22px 26px; margin-top: 30px; box-shadow: 0 12px 30px rgba(0,0,0,0.6); text-align: center;">
            <div style="font-size: 26px; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px;">Nexo Analytics</div>
            <div style="font-size: 13.5px; color: #38bdf8; font-weight: 700; letter-spacing: 1px; margin-top: 4px; text-transform: uppercase;">Portal de Acceso Seguro · Airtable Cloud & 2FA</div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")

        # -------------------------------------------------------------
        # PASO 1: LOGIN PRINCIPAL (EMAIL + CONTRASEÑA)
        # -------------------------------------------------------------
        if step == "LOGIN":
            tab_login, tab_forgot, tab_register = st.tabs([
                "🔑 Iniciar Sesión",
                "🔄 Olvidé mi Contraseña",
                "Crear cuenta",
            ])

            with tab_login:
                email_in = st.text_input("Email * (Requerido):", key="login_email_input", placeholder="Email (ej. usuario@correo.com)").strip().lower()
                email_login_valid = bool(email_in and is_valid_email(email_in))

                if email_in and not email_login_valid:
                    st.error("Ingresa un correo electrónico con formato válido.")

                # Cartelito inmediato cuando el usuario pone su correo si su contraseña fue reestablecida
                reset_pending = False
                if email_login_valid:
                    user_peek = find_user_by_email(email_in)
                    if user_peek and user_peek.get("reset_generico"):
                        reset_pending = True
                        st.markdown("""
                        <div style="background: rgba(245, 158, 11, 0.18); border: 1.5px solid #f59e0b; border-radius: 10px; padding: 14px 18px; margin: 10px 0 16px 0;">
                            <div style="display: flex; align-items: flex-start; gap: 12px;">
                                <span style="font-size: 24px; line-height: 1;">🔔</span>
                                <div>
                                    <div style="font-size: 15px; font-weight: 800; color: #fbbf24; letter-spacing: -0.2px;">Tu contraseña ha sido reestablecida</div>
                                    <div style="font-size: 13.5px; color: #fde68a; margin-top: 4px; line-height: 1.45;">
                                        Un administrador ha reestablecido el acceso a tu cuenta. Ingresa con la clave genérica asignada (<code>Consultora2026!</code>) y podrás configurar inmediatamente tu nueva contraseña personal segura.
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with st.form("form_login_airtable"):
                    pwd_label = "Contraseña Genérica Asignada * (Requerida):" if reset_pending else "Contraseña * (Requerida):"
                    pwd_hint = "Contraseña (6 a 20 caracteres)"
                    pwd_in = st.text_input(
                        pwd_label,
                        type="password",
                        placeholder=pwd_hint if email_login_valid else "🔒 Ingrese un correo electrónico válido primero",
                        disabled=not email_login_valid
                    )
                    btn_submit = st.form_submit_button(
                        "Entrar",
                        type="primary",
                        use_container_width=True,
                        disabled=not email_login_valid
                    )

                    if btn_submit:
                        if not email_in or not is_valid_email(email_in):
                            st.error("Ingresa un correo electrónico con formato válido.")
                        elif len(pwd_in) < 6 or len(pwd_in) > 20:
                            st.error("La contraseña debe tener entre 6 y 20 caracteres.")
                        else:
                            # Control Anti-Fuerza Bruta
                            allowed, wait_sec = check_login_rate_limit(email_in)
                            if not allowed:
                                st.error(f"⛔ Cuenta/IP bloqueada por demasiados intentos fallidos. Intente nuevamente en {wait_sec // 60 + 1} minutos.")
                            else:
                                with st.spinner("Verificando credenciales en Airtable..."):
                                    ok, status_code, user_data = authenticate_user_with_airtable(email_in, pwd_in)

                                if not ok and status_code not in ("REQUIERE_2FA_CODE", "SETUP_2FA_REQUERIDO", "RESET_GENERICO_ACTIVO"):
                                    record_failed_login(email_in)
                                    st.error(status_code)
                                elif status_code == "AUTENTICADO":
                                    st.session_state["current_user"] = user_data
                                    token = create_encrypted_client_session_token(user_data)
                                    _inject_storage_vault_saver(token)
                                    st.session_state["auth_flow_step"] = "LOGIN"
                                    st.success("✓ Acceso concedido.")
                                    st.rerun()
                                elif status_code == "REQUIERE_2FA_CODE":
                                    st.session_state["pending_user"] = user_data
                                    st.session_state["auth_flow_step"] = "2FA_VERIFY"
                                    st.rerun()
                                elif status_code == "SETUP_2FA_REQUERIDO":
                                    st.session_state["pending_user"] = user_data
                                    st.session_state["setup_secret"] = generate_totp_secret()
                                    st.session_state["auth_flow_step"] = "2FA_SETUP"
                                    st.rerun()
                                elif status_code == "RESET_GENERICO_ACTIVO":
                                    st.session_state["pending_user"] = user_data
                                    st.session_state["auth_flow_step"] = "RESET_GENERICO"
                                    st.rerun()


            with tab_forgot:
                st.markdown("##### Recuperación con Google Authenticator")
                st.caption("Si olvidaste tu contraseña, define una nueva ingresando el código de tu aplicación de autenticación.")
                
                f_email = st.text_input("Tu Correo Registrado * (Requerido):", key="recup_email", placeholder="usuario@empresa.com (Requerido)").strip().lower()
                f_email_valid = bool(f_email and is_valid_email(f_email))

                if f_email and not f_email_valid:
                    st.error(f"⚠️ El correo '{f_email}' no es válido (ejemplo: usuario@empresa.com). Ingrese un correo válido para habilitar la nueva contraseña.")
                elif not f_email:
                    st.caption("ℹ️ Ingrese su correo registrado para habilitar los siguientes pasos.")

                f_new_pwd = st.text_input(
                    "Nueva Contraseña * (Requerida):",
                    key="recup_pwd",
                    type="password",
                    placeholder="••••••••••••" if f_email_valid else "🔒 Ingrese un correo válido primero para habilitar",
                    disabled=not f_email_valid
                )
                if f_email_valid:
                    req_ok_f = render_password_requirements_card(f_new_pwd)
                else:
                    req_ok_f = False

                pwd_ready = bool(f_email_valid and req_ok_f)
                f_new_pwd_rep = st.text_input(
                    "Repetir Nueva Contraseña * (Requerida):",
                    key="recup_pwd_rep",
                    type="password",
                    placeholder="••••••••••••" if pwd_ready else "🔒 Cumpla los requisitos de contraseña primero",
                    disabled=not pwd_ready
                )

                rep_ready = False
                if pwd_ready:
                    if f_new_pwd_rep:
                        if f_new_pwd == f_new_pwd_rep:
                            rep_ready = True
                            st.caption("✓ Las contraseñas coinciden.")
                        else:
                            st.error("⚠️ Las contraseñas no coinciden.")
                    else:
                        st.caption("ℹ️ Repita la nueva contraseña para continuar.")

                totp_ready = bool(rep_ready)
                f_totp = st.text_input(
                    "Código de 6 dígitos de Google Authenticator * (Requerido):",
                    key="recup_totp",
                    max_chars=6,
                    placeholder="123456" if totp_ready else "🔒 Complete las contraseñas primero",
                    disabled=not totp_ready
                ).strip()

                can_recup = bool(totp_ready and len(f_totp) == 6 and f_totp.isdigit())
                btn_recup = st.button(
                    "Reestablecer Contraseña",
                    key="btn_recup_submit",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_recup
                )

                if btn_recup:
                    if not f_email:
                        st.error("El correo electrónico es un campo obligatorio.")
                    elif not is_valid_email(f_email):
                        st.error(f"El correo '{f_email}' no tiene un formato válido (ejemplo: usuario@empresa.com).")
                    elif not f_new_pwd:
                        st.error("La nueva contraseña es obligatoria.")
                    elif not req_ok_f:
                        st.error("La nueva contraseña no cumple con todos los requisitos de seguridad obligatorios.")
                    elif not f_new_pwd_rep:
                        st.error("Debe repetir la nueva contraseña.")
                    elif f_new_pwd != f_new_pwd_rep:
                        st.error("Las contraseñas no coinciden.")
                    elif not f_totp:
                        st.error("El código 2FA de Google Authenticator es obligatorio.")
                    elif len(f_totp) != 6 or not f_totp.isdigit():
                        st.error("El código 2FA debe constar exactamente de 6 dígitos numéricos.")
                    else:
                        with st.spinner("Validando 2FA y actualizando Airtable..."):
                            ok_res, msg_res = reset_password_via_2fa(f_email, f_totp, f_new_pwd)
                        if ok_res:
                            st.success(f"✓ {msg_res}")
                        else:
                            st.error(msg_res)

            with tab_register:
                st.markdown("#### Crear cuenta")

                # Control de Administrador Único: Solo puede haber 1 en todo el sistema
                current_cloud_users = fetch_all_users()
                has_registered_admin = any(str(u.get("rol", "")).lower() == "admin" for u in current_cloud_users)

                if not has_registered_admin:
                    st.markdown("""
                    <div style="background: rgba(56, 189, 248, 0.12); border: 1.5px solid #38bdf8; border-radius: 10px; padding: 12px 16px; margin-bottom: 15px;">
                        <div style="font-weight: 800; color: #38bdf8; font-size: 14.5px;">👑 Configuración de Administrador Único</div>
                        <div style="font-size: 13px; color: #bae6fd; margin-top: 3px;">
                            Aún no existe una cuenta de administrador registrada en el sistema. Esta cuenta inicial se registrará como el <b>Administrador Principal y Único</b>.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    r_role = "admin"
                else:
                    st.caption("ℹ️ El rol de Administrador ya se encuentra asignado y protegido. Selecciona tu perfil operativo:")
                    r_role = st.selectbox("Rol Asignado:", ["closer", "viewer", "manager"], key="reg_role", index=0)

                # Paso 1: Nombre completo o alias
                r_name = st.text_input("Nombre o alias * (3 a 40 caracteres):", key="reg_name", placeholder="Nombre o alias (3 a 40 caracteres)").strip()
                name_valid = bool(r_name and 3 <= len(r_name) <= 40)

                if r_name and not name_valid:
                    st.warning("⚠️ El nombre debe contener al menos 3 caracteres.")
                elif not r_name:
                    st.caption("ℹ️ Campo obligatorio (*). Ingresa tu nombre o alias para habilitar el email.")

                # Paso 2: Correo electrónico (se habilita ÚNICAMENTE con el nombre completo válido)
                email_disabled = not name_valid
                r_email = st.text_input(
                    "Email * (Requerido):",
                    key="reg_email",
                    placeholder="Email (ej. usuario@correo.com)" if name_valid else "🔒 Completa tu nombre primero para habilitar este campo",
                    disabled=email_disabled
                ).strip().lower()

                email_valid = False
                if name_valid:
                    if r_email:
                        if is_valid_email(r_email):
                            email_valid = True
                            st.caption("✓ Correo con formato válido")
                        else:
                            st.error("Ingresa un correo electrónico con formato válido.")
                    else:
                        st.caption("ℹ️ Campo obligatorio (*). Ingresa tu correo electrónico para habilitar los campos de contraseña.")

                # Paso 3: Contraseña (se habilita ÚNICAMENTE si el correo es válido)
                pwd_disabled = not email_valid
                r_pwd = st.text_input(
                    "Contraseña * (6 a 20 caracteres):",
                    key="reg_pwd",
                    type="password",
                    placeholder="Contraseña (6 a 20 caracteres)" if email_valid else "🔒 Ingresa un correo electrónico válido primero para habilitar",
                    disabled=pwd_disabled
                )

                # Tarjeta dinámica de requisitos de seguridad solicitada (solo activa y visible si correo es válido)
                if email_valid:
                    reqs_ok = render_password_requirements_card(r_pwd)
                else:
                    reqs_ok = False

                # Paso 4: Repetir contraseña (se habilita junto con contraseña al validar el correo)
                pwd_rep_disabled = not email_valid
                r_pwd_rep = st.text_input(
                    "Repetir contraseña * (6 a 20 caracteres):",
                    key="reg_pwd_rep",
                    type="password",
                    placeholder="Repetir contraseña (6 a 20 caracteres)" if email_valid else "🔒 Ingresa un correo electrónico válido primero",
                    disabled=pwd_rep_disabled
                )

                if email_valid and r_pwd and r_pwd_rep:
                    if r_pwd == r_pwd_rep:
                        st.caption("✓ Las contraseñas coinciden.")
                    else:
                        st.error("Las contraseñas no coinciden.")

                # Inyectar guardián progresivo en tiempo real para el navegador
                _inject_progressive_form_guard()

                btn_reg = st.button(
                    "Registrarme",
                    type="primary",
                    use_container_width=True,
                    key="btn_submit_register"
                )

                if btn_reg:
                    reg_err = validate_registration_fields(r_name, r_email, r_pwd, r_pwd_rep)
                    if reg_err:
                        st.error(f"⚠️ {reg_err}")
                    else:
                        with st.spinner("Creando usuario en Airtable con cifrado..."):
                            ok_reg, msg_reg, created_user = create_airtable_user(
                                email=r_email,
                                nombre=r_name,
                                password=r_pwd,
                                rol=r_role,
                                activo=True,
                                reset_generico=False,
                            )
                        if ok_reg and created_user:
                            st.session_state["pending_user"] = created_user
                            st.session_state["setup_secret"] = created_user["totp_secret_raw"]
                            st.session_state["auth_flow_step"] = "2FA_SETUP"
                            st.rerun()
                        else:
                            st.error(msg_reg)

        # -------------------------------------------------------------
        # PASO 2: VERIFICACIÓN 2FA (USUARIO CON 2FA YA HABILITADO)
        # -------------------------------------------------------------
        elif step == "2FA_VERIFY":
            user = st.session_state.get("pending_user", {})
            st.markdown(f"#### 🔐 Verificación en Dos Pasos")
            st.markdown(f"Usuario: **{user.get('nombre')}** (`{user.get('email')}`)")
            st.caption("Abre la app **Google Authenticator** en tu celular e ingresa el código de 6 dígitos:")

            with st.form("form_verify_totp"):
                code_in = st.text_input("Código de 6 dígitos:", max_chars=6, placeholder="123456").strip()
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    btn_ok = st.form_submit_button("Verificar e Ingresar", type="primary", use_container_width=True)
                with col_b2:
                    btn_cancel = st.form_submit_button("Volver", use_container_width=True)

                if btn_cancel:
                    st.session_state["auth_flow_step"] = "LOGIN"
                    st.session_state["pending_user"] = None
                    st.rerun()

                if btn_ok:
                    if not code_in:
                        st.error("El código 2FA es obligatorio.")
                    elif len(code_in) != 6 or not code_in.isdigit():
                        st.error("El código 2FA debe constar exactamente de 6 dígitos numéricos.")
                    else:
                        encrypted_secret = user.get("totp_secret_encrypted")
                        try:
                            raw_secret = decrypt_field(encrypted_secret)
                        except Exception as e:
                            st.error(f"Error de seguridad: {e}")
                            raw_secret = None

                        if raw_secret and verify_totp_code(raw_secret, code_in):
                            # Éxito: Limpiar intentos fallidos y generar token cifrado para sessionStorage/localStorage
                            clear_failed_logins(user.get("email"))
                            sec_token = create_encrypted_client_session_token(user)

                            st.session_state["current_user"] = {
                                "id": user.get("record_id"),
                                "username": user.get("email"),
                                "full_name": user.get("nombre", user.get("email")),
                                "role": user.get("rol", "closer"),
                                "email": user.get("email"),
                                "must_change_password": False,
                                "last_activity": time.time(),
                            }
                            st.query_params["_st_sec_vault"] = sec_token
                            _inject_storage_vault_saver(sec_token)

                            st.session_state["auth_flow_step"] = "LOGIN"
                            st.session_state["pending_user"] = None
                            st.success(f"✓ Identidad confirmada. Bienvenido, {user.get('nombre')}.")
                            st.rerun()
                        else:
                            record_failed_login(user.get("email", "unknown"))
                            st.error("Código 2FA incorrecto o expirado. Verifique que la hora de su celular esté sincronizada.")

        # -------------------------------------------------------------
        # PASO 3: ENROLAMIENTO INICIAL 2FA (PRIMERA VEZ)
        # -------------------------------------------------------------
        elif step == "2FA_SETUP":
            user = st.session_state.get("pending_user", {})
            secret = st.session_state.get("setup_secret", "")
            uri = get_totp_uri(secret, user.get("email", "usuario"))
            qr_bytes = generate_qr_code_image_bytes(uri)

            st.markdown("#### 📱 Vincular Google Authenticator")
            st.info("Para proteger tu cuenta, escanea este código QR con la app **Google Authenticator** en tu celular:")

            c_qr1, c_qr2, c_qr3 = st.columns([1, 2, 1])
            with c_qr2:
                st.image(qr_bytes, width=220)

            with st.expander("¿No puedes escanear el QR?"):
                st.caption("Introduce esta clave manual en tu app:")
                st.code(secret, language="text")

            with st.form("form_activate_2fa"):
                confirm_code = st.text_input("Código de 6 dígitos que muestra tu app:", max_chars=6, placeholder="123456").strip()
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    btn_activate = st.form_submit_button("Activar 2FA e Ingresar", type="primary", use_container_width=True)
                with col_a2:
                    btn_cancel_act = st.form_submit_button("Cancelar", use_container_width=True)

                if btn_cancel_act:
                    st.session_state["auth_flow_step"] = "LOGIN"
                    st.session_state["pending_user"] = None
                    st.rerun()

                if btn_activate:
                    if not confirm_code:
                        st.error("El código 2FA de Google Authenticator es obligatorio.")
                    elif len(confirm_code) != 6 or not confirm_code.isdigit():
                        st.error("El código 2FA debe constar exactamente de 6 dígitos numéricos.")
                    else:
                        with st.spinner("Validando código y activando 2FA en Airtable..."):
                            ok_act, msg_act = activate_user_2fa(
                                record_id=user["record_id"],
                                raw_secret=secret,
                                totp_code=confirm_code,
                            )
                        if ok_act:
                            clear_failed_logins(user.get("email"))
                            sec_token = create_encrypted_client_session_token(user)

                            st.session_state["current_user"] = {
                                "id": user.get("record_id"),
                                "username": user.get("email"),
                                "full_name": user.get("nombre", user.get("email")),
                                "role": user.get("rol", "closer"),
                                "email": user.get("email"),
                                "must_change_password": False,
                                "last_activity": time.time(),
                            }
                            st.query_params["_st_sec_vault"] = sec_token
                            _inject_storage_vault_saver(sec_token)

                            st.session_state["auth_flow_step"] = "LOGIN"
                            st.session_state["pending_user"] = None
                            st.success("✓ 2FA activado con éxito. Ingresando...")
                            st.rerun()
                        else:
                            st.error(msg_act)

        # -------------------------------------------------------------
        # PASO 4: RESETEO GENÉRICO (LLAVE MAESTRA AIRTABLE)
        # -------------------------------------------------------------
        elif step == "RESET_GENERICO":
            user = st.session_state.get("pending_user", {})
            st.markdown("""
            <div style="background: rgba(245, 158, 11, 0.2); border: 1.5px solid #f59e0b; border-radius: 10px; padding: 14px 18px; margin-bottom: 15px;">
                <div style="font-size: 16px; font-weight: 800; color: #fbbf24;">🔔 Tu contraseña ha sido reestablecida</div>
                <div style="font-size: 13.5px; color: #fde68a; margin-top: 4px; line-height: 1.45;">
                    Has ingresado con la clave genérica asignada para tu cuenta. Por políticas estrictas de ciberseguridad, define a continuación tu nueva contraseña segura personal.
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"Cuenta: **{user.get('nombre')}** (`{user.get('email')}`)")

            has_2fa = user.get("totp_enabled") and user.get("totp_secret_encrypted")
            
            # Si no tenía 2FA, generamos uno nuevo para que lo vincule
            if not has_2fa:
                if "setup_secret" not in st.session_state or not st.session_state["setup_secret"]:
                    st.session_state["setup_secret"] = generate_totp_secret()
                secret_res = st.session_state["setup_secret"]
                uri_res = get_totp_uri(secret_res, user.get("email", "usuario"))
                qr_res = generate_qr_code_image_bytes(uri_res)
                st.info("Escanea este código QR con Google Authenticator para tu segundo factor:")
                st.image(qr_res, width=200)

            c_pwd1 = st.text_input("Nueva Contraseña Definitiva:", key="reset_g_pwd", type="password", placeholder="••••••••")
            req_ok_g = render_password_requirements_card(c_pwd1)
            c_pwd2 = st.text_input("Repetir Nueva Contraseña:", key="reset_g_pwd_rep", type="password", placeholder="••••••••")
            c_totp = st.text_input("Código de 6 dígitos de Google Authenticator:", key="reset_g_totp", max_chars=6, placeholder="123456").strip()
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                btn_save_reset = st.button("Guardar Contraseña y Continuar", type="primary", use_container_width=True, key="btn_save_reset_g")
            with col_g2:
                btn_back_reset = st.button("Cancelar", use_container_width=True, key="btn_cancel_reset_g")

            if btn_back_reset:
                st.session_state["auth_flow_step"] = "LOGIN"
                st.session_state["pending_user"] = None
                st.rerun()

            if btn_save_reset:
                if not c_pwd1:
                    st.error("La nueva contraseña es obligatoria.")
                elif not req_ok_g:
                    st.error("La contraseña no cumple con todos los requisitos de seguridad obligatorios.")
                elif not c_pwd2:
                    st.error("Debe repetir la nueva contraseña.")
                elif c_pwd1 != c_pwd2:
                    st.error("Las contraseñas no coinciden.")
                elif not c_totp:
                    st.error("El código 2FA de Google Authenticator es obligatorio.")
                elif len(c_totp) != 6 or not c_totp.isdigit():
                    st.error("El código 2FA debe constar exactamente de 6 dígitos numéricos.")
                else:
                    with st.spinner("Actualizando credenciales en Airtable..."):
                        if has_2fa:
                            ok_g, msg_g = reset_password_via_2fa(user["email"], c_totp, c_pwd1)
                        else:
                            ok_g, msg_g = activate_user_2fa(
                                record_id=user["record_id"],
                                raw_secret=secret_res,
                                totp_code=c_totp,
                                new_password=c_pwd1,
                            )
                    if ok_g:
                        clear_failed_logins(user.get("email"))
                        sec_token = create_encrypted_client_session_token(user)

                        st.session_state["current_user"] = {
                            "id": user.get("record_id"),
                            "username": user.get("email"),
                            "full_name": user.get("nombre", user.get("email")),
                            "role": user.get("rol", "closer"),
                            "email": user.get("email"),
                            "must_change_password": False,
                            "last_activity": time.time(),
                        }
                        st.query_params["_st_sec_vault"] = sec_token
                        _inject_storage_vault_saver(sec_token)

                        st.session_state["auth_flow_step"] = "LOGIN"
                        st.session_state["pending_user"] = None
                        st.success("✓ Contraseña actualizada y reseteo genérico desactivado en Airtable.")
                        st.rerun()
                    else:
                        st.error(msg_g)

    return False


def logout_user():
    """Cierra la sesión del usuario actual, limpia la memoria y purga el almacenamiento."""
    st.session_state["current_user"] = None
    st.session_state["auth_flow_step"] = "LOGIN"
    st.session_state["logged_out"] = True
    st.query_params.clear()
    _inject_storage_vault_cleaner()
    st.rerun()


def render_user_sidebar_badge():
    """Muestra la tarjeta de perfil del usuario logueado en la barra lateral con botón para cerrar sesión."""
    user = st.session_state.get("current_user")
    if not user:
        return

    role_colors = {
        "admin": "#ef4444",
        "manager": "#f59e0b",
        "closer": "#38bdf8",
        "viewer": "#10b981",
    }
    badge_color = role_colors.get(user.get("role", "closer"), "#94a3b8")
    display_name = user.get("full_name") or user.get("email") or "Usuario"
    user_email = user.get("email") or ""
    role_name = user.get("role", "closer").upper()

    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; border-left: 4.5px solid {badge_color};">
        <div style="font-size: 16px; font-weight: 700; color: #f8fafc;">{display_name}</div>
        <div style="font-size: 13px; color: #94a3b8; margin-top: 1px;">{user_email}</div>
        <div style="font-size: 13px; color: {badge_color}; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-top: 4px;">Rol: {role_name}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout_sidebar"):
        logout_user()


def render_user_header_badge():
    """Muestra un badge compacto de usuario y botón de cerrar sesión en la cabecera superior derecha."""
    user = st.session_state.get("current_user")
    if not user:
        return

    role_colors = {
        "admin": "#ef4444",
        "manager": "#f59e0b",
        "closer": "#38bdf8",
        "viewer": "#10b981",
    }
    badge_color = role_colors.get(user.get("role", "closer"), "#94a3b8")
    display_name = user.get("full_name") or user.get("email") or "Usuario"
    role_name = user.get("role", "closer").upper()

    col_info, col_btn = st.columns([1.5, 1.3], vertical_alignment="center")
    with col_info:
        st.markdown(f"""
        <div style="text-align: right; padding-right: 6px;">
            <div style="font-size: 14.5px; font-weight: 700; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">👤 {display_name}</div>
            <div style="font-size: 12px; color: {badge_color}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">{role_name}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_btn:
        if st.button("🚪 Cerrar Sesión", key="btn_logout_header", use_container_width=True):
            logout_user()

