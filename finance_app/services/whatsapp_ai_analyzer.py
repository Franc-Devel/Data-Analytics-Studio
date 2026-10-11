"""
Nexo Analytics - Motor de Inteligencia Artificial para Análisis y Segmentación de Historial de WhatsApp.
Procesa el historial completo de conversaciones, discrimina intenciones, requerimientos técnicos,
cultivos, objeciones y correlaciona con campañas publicitarias y fechas.
"""

from __future__ import annotations
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("whatsapp_ai_analyzer")


# =========================================================================
# PATRONES SEMÁNTICOS Y REGLAS DE NLP
# =========================================================================

PRODUCT_RULES = {
    "Sondas Sentek (Humedad & Riego)": [
        r"sentek", r"\bsonda\b", r"\bsondas\b", r"drill\s*&\s*drop", r"drill",
        r"humedad.*suelo", r"perfil.*humedad", r"irrimax", r"capacitiva",
        r"60\s*cm", r"90\s*cm", r"120\s*cm", r"60cm", r"90cm", r"120cm"
    ],
    "Estaciones Davis Instruments": [
        r"davis", r"vantage\s*pro", r"vantage\s*vue", r"vantage", r"weatherlink",
        r"estaci[oó]n\s*met", r"anem[oó]metro", r"pluvi[oó]metro", r"\bvue\b",
        r"veleta", r"tasa.*lluvia", r"rain\s*rate"
    ],
    "Automatismo & Fertirriego (Galcon Agro / GSI)": [
        r"\bgsi\b", r"gsi\s*pro", r"automatismo", r"fertirriego", r"inyector",
        r"inyecci[oó]n", r"tubo.*comando", r"fertikit", r"fertiquit", r"panel.*solar.*riego",
        r"osmosis.*inversa", r"\b[oó]smosis\b"
    ],
    "Controladores Jardinería (Galcon 9001BT)": [
        r"9001", r"9001bt", r"7001", r"galcon.*jardin", r"jardiner[ií]a",
        r"programador.*canilla", r"riego.*jardin", r"bater[ií]a.*riego"
    ],
    "Válvulas Hidráulicas (Raphael)": [
        r"raphael", r"v[aá]lvula.*hidr[aá]ul", r"v[aá]lvula.*alivio",
        r"v[aá]lvula.*retenci[oó]n", r"diafragma.*raphael", r"cabezal.*filtrado"
    ],
    "Caudalímetros & Fertímetros": [
        r"caudal[ií]metro", r"\bcaudal\b", r"totalizador", r"fert[ií]metro",
        r"no\s*invasivo", r"ultras[oó]nico", r"medidor.*agua", r"cañer[ií]a.*pvc"
    ],
}

INTENT_RULES = {
    "💰 Presupuesto / Cotización / Precios": [
        r"\bprecio\b", r"\bprecios\b", r"cu[aá]nto\s*(est[aá]|sale|cuesta|vale)",
        r"cotiz", r"presupuest", r"\bvalor\b", r"\bcosto\b", r"lista.*precios"
    ],
    "📐 Asesoramiento Técnico / Factibilidad": [
        r"c[oó]mo\s*funciona", r"sirve\s*para", r"compatib", r"alcance.*se[ñn]al",
        r"distancia", r"instalaci[oó]n", r"se[ñn]al.*celular", r"chip.*davis",
        r"profundidad.*raiz", r"curva.*humedad", r"datos.*nube"
    ],
    "📦 Disponibilidad / Stock / Entrega Inmediata": [
        r"\bstock\b", r"disponib", r"cu[aá]ndo\s*llega", r"entrega\s*inmediata",
        r"demora", r"plazo.*entrega", r"env[ií]o", r"despacho", r"gu[ií]a"
    ],
    "📄 Catálogo / Ficha Técnica / Manual": [
        r"cat[aá]logo", r"ficha\s*t[eé]cnica", r"manual", r"folleto", r"fotofolleto",
        r"\bpdf\b", r"especificaci[oó]n", r"enviar.*correo", r"por\s*mail"
    ],
    "🤝 Reunión / Demo Meet / Llamada Técnica": [
        r"\bmeet\b", r"reuni[oó]n", r"llamada", r"coordinar", r"videollamada",
        r"\bzoom\b", r"llamame", r"charlar", r"agendar"
    ],
    "💳 Financiación / Formas de Pago": [
        r"forma.*pago", r"cuotas", r"financiaci[oó]n", r"cheque", r"e-cheq",
        r"factura", r"d[oó]lar.*oficial", r"d[oó]lar.*billete", r"leasing",
        r"transferencia"
    ],
    "🔧 Soporte Técnico / Reparación / Repuestos": [
        r"repuesto", r"service", r"reparaci[oó]n", r"\bfalla\b", r"calibraci[oó]n",
        r"no\s*funciona", r"garant[ií]a", r"rotura"
    ],
}

CROP_RULES = {
    "Frutilla": [r"frutilla", r"frutillas"],
    "Kiwi": [r"\bkiwi\b", r"kiwis"],
    "Papa": [r"\bpapa\b", r"\bpapas\b"],
    "Nuez Pecán": [r"pec[aá]n", r"pecan"],
    "Viñedos / Uva": [r"vi[ñn]a", r"vi[ñn]edo", r"parral", r"\buva\b", r"bodega"],
    "Olivo": [r"\bolivo\b", r"\bolivos\b", r"olivar"],
    "Frambuesa / Berries": [r"frambuesa", r"\bmora\b", r"ar[aá]ndano", r"berries"],
    "Extensivos (Maíz, Soja, Trigo, Girasol)": [
        r"\bma[ií]z\b", r"\bsoja\b", r"\btrigo\b", r"girasol", r"camelina", r"centeno", r"avena"
    ],
    "Colza": [r"\bcolza\b"],
    "Maní": [r"man[ií]"],
    "Cebolla / Ajo / Hortalizas": [r"cebolla", r"\bajo\b", r"zanahoria", r"hortaliza", r"invernadero"],
    "Yerba Mate": [r"yerba.*mate", r"\byerba\b"],
    "Parque / Jardín Residencial": [r"jard[ií]n", r"\bcesped\b", r"\bcésped\b", r"\bparque\b"],
}

OBJECTION_RULES = {
    "Precio / Comparación Competencia": [
        r"precio.*alto", r"caro", r"hunter", r"rainbird", r"diferencia.*precio", r"otra.*propuesta"
    ],
    "Falta de Financiación / Solo Transferencia": [
        r"no puedo.*transferencia", r"solo transferencia", r"necesito cuotas", r"financiaci"
    ],
    "Dudas sobre Cobertura / Señal Celular": [
        r"baja.*se[ñn]al", r"sin.*se[ñn]al", r"no hay.*se[ñn]al", r"distancia.*300", r"distancia.*alcance"
    ],
    "Fallas en Software Satelital (Kilimo)": [
        r"kilimo", r"estimaciones no son exactas", r"muchas perdidas"
    ],
}


# =========================================================================
# MOTOR PRINCIPAL DE ANÁLISIS DEL HISTORIAL
# =========================================================================

def load_whatsapp_raw_messages() -> List[Dict[str, Any]]:
    """Carga los mensajes de WhatsApp sin procesar desde whatsapp_inbox/live_incoming_messages.json."""
    inbox_file = Path("whatsapp_inbox/live_incoming_messages.json")
    if not inbox_file.exists():
        return []
    try:
        with open(inbox_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error al leer live_incoming_messages.json: {e}", exc_info=True)
        return []


def load_contacts_mapping() -> Dict[str, str]:
    """Carga el mapa de LID a teléfono real desde contacts_cache.json."""
    cache_file = Path("whatsapp_inbox/contacts_cache.json")
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return cache.get("lidToPhoneMap", {})
    except Exception as e:
        logger.error(f"Error al leer contacts_cache.json: {e}", exc_info=True)
        return {}


def analyze_all_whatsapp_conversations(
    master_leads_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Lee todo el historial completo de chats, agrupa por cliente, discrimina demandas
    técnicas, productos, intenciones, cultivos, objeciones y correlaciona con campañas y fechas.
    Retorna un DataFrame enriquecido con 1 fila por conversación.
    """
    raw_msgs = load_whatsapp_raw_messages()
    if not raw_msgs:
        return pd.DataFrame()

    lid_map = load_contacts_mapping()

    # Mapeo rápido de Leads CRM existentes para cruce de campaña y ubicación
    leads_lookup: Dict[str, Dict[str, Any]] = {}
    if master_leads_df is not None and not master_leads_df.empty:
        for _, row in master_leads_df.iterrows():
            tel = str(row.get("Telefono", ""))
            clean_digits = re.sub(r"\D", "", tel)[-8:]
            if len(clean_digits) >= 6:
                leads_lookup[clean_digits] = row.to_dict()

    # 1. Agrupar mensajes por cliente / número
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for m in raw_msgs:
        raw_phone = m.get("phone") or "Desconocido"
        clean_target = lid_map.get(raw_phone, raw_phone)
        grouped.setdefault(clean_target, []).append(m)

    records = []

    for phone, m_list in grouped.items():
        # Ordenar mensajes cronológicamente
        m_list_sorted = sorted(
            m_list,
            key=lambda x: str(x.get("timestamp") or ""),
        )

        incoming_texts = [
            str(m.get("text", "")).strip()
            for m in m_list_sorted
            if not m.get("is_from_me") and not m.get("fromMe") and m.get("text")
        ]
        all_texts = [
            str(m.get("text", "")).strip()
            for m in m_list_sorted
            if m.get("text")
        ]

        if not all_texts:
            continue

        full_incoming_concat = " \n ".join(incoming_texts)
        full_all_concat = " \n ".join(all_texts)

        # Determinar nombre del cliente
        client_name = None
        for m in m_list_sorted:
            candidate = m.get("name") or m.get("push_name")
            if candidate and candidate not in ("Desconocido", "Cliente WhatsApp", "Cliente"):
                client_name = candidate
                break

        # Buscar cruce con CRM
        phone_digits = re.sub(r"\D", "", phone)[-8:]
        crm_lead = leads_lookup.get(phone_digits, {})
        if not client_name and crm_lead:
            client_name = crm_lead.get("Contacto")
        if not client_name:
            client_name = f"Cliente {phone}"

        # Fechas
        ts_valid = []
        for m in m_list_sorted:
            raw_ts = m.get("timestamp")
            if raw_ts:
                t = pd.to_datetime(raw_ts, errors="coerce")
                if pd.notna(t):
                    if getattr(t, "tzinfo", None) is not None:
                        t = t.tz_localize(None)
                    ts_valid.append(t)

        first_date = min(ts_valid) if ts_valid else pd.NaT
        last_date = max(ts_valid) if ts_valid else pd.NaT

        # =========================================================
        # DISCRIMINACIÓN SEMÁNTICA: QUÉ PIDE EL CLIENTE
        # =========================================================

        # 1. Productos Detectados
        detected_products = []
        for prod_cat, patterns in PRODUCT_RULES.items():
            if any(re.search(pat, full_all_concat, re.IGNORECASE) for pat in patterns):
                detected_products.append(prod_cat)

        if not detected_products:
            # Fallback por cruce de producto en CRM
            crm_prod = str(crm_lead.get("Linea_Producto", "")).strip()
            if crm_prod and crm_prod not in ("General", "Sin Especificar", "nan"):
                for p_rule in PRODUCT_RULES:
                    if crm_prod.lower() in p_rule.lower():
                        detected_products.append(p_rule)
                        break

        producto_principal = detected_products[0] if detected_products else "Consulta General / Otros"

        # 2. Intenciones Comerciales
        detected_intents = []
        for intent_cat, patterns in INTENT_RULES.items():
            if any(re.search(pat, full_incoming_concat, re.IGNORECASE) for pat in patterns):
                detected_intents.append(intent_cat)

        intencion_principal = detected_intents[0] if detected_intents else "Consulta General"

        # 3. Cultivo / Actividad Agrícola
        detected_crops = []
        for crop_name, patterns in CROP_RULES.items():
            if any(re.search(pat, full_all_concat, re.IGNORECASE) for pat in patterns):
                detected_crops.append(crop_name)
        cultivo_str = ", ".join(detected_crops) if detected_crops else "No especificado"

        # 4. Objeciones Detectadas
        detected_objections = []
        for obj_name, patterns in OBJECTION_RULES.items():
            if any(re.search(pat, full_incoming_concat, re.IGNORECASE) for pat in patterns):
                detected_objections.append(obj_name)
        objecion_str = ", ".join(detected_objections) if detected_objections else "Ninguna detectada"

        # 5. Determinación de Campaña de Origen
        is_remarketing = bool(crm_lead.get("Remarketing") == 1)
        if is_remarketing:
            campana = "Meta Ads · Remarketing (01/06/26)"
        elif "Davis" in producto_principal:
            campana = "Meta Ads · Davis Instruments"
        elif "Sentek" in producto_principal:
            campana = "Meta Ads · Sentek Sondas"
        elif "Jardinería" in producto_principal:
            campana = "Meta Ads · Jardinería (9001BT)"
        elif "Raphael" in producto_principal:
            campana = "Meta Ads · Raphael Válvulas"
        elif "Automatismo" in producto_principal or "Caudal" in producto_principal:
            campana = "Meta Ads · Automatismo & GSI"
        elif crm_lead.get("Region") in ("Norte", "NOA", "NEA"):
            campana = "Meta Ads regional · Norte"
        elif crm_lead.get("Region") == "Sur" or crm_lead.get("Provincia") in ("Chubut", "Río Negro", "Neuquén"):
            campana = "Meta Ads regional · Sur"
        else:
            campana = "Orgánico / WhatsApp Directo"

        # 6. Temperatura / Prioridad
        is_hot = (
            any("Presupuesto" in i or "Reunión" in i or "Stock" in i for i in detected_intents)
            or len(detected_crops) > 0
            or crm_lead.get("Lead_Score", 0) >= 70
        )
        is_cold = (
            any(re.search(r"no deseo|no interesa|descartar|no por ahora", full_incoming_concat, re.IGNORECASE) for _ in [1])
            or len(incoming_texts) == 0
        )
        if is_cold:
            temperatura = "❄️ Cold (Baja Prioridad)"
        elif is_hot:
            temperatura = "🔥 Hot (Alta Prioridad / En Cierre)"
        else:
            temperatura = "⚡ Warm (En Seguimiento)"

        # 7. Resumen Ejecutivo en Lenguaje Natural de qué pide el usuario
        resumen_que_pide = _generate_ai_demand_summary(
            client_name=client_name,
            product=producto_principal,
            intents=detected_intents,
            crops=detected_crops,
            objections=detected_objections,
            incoming_sample=incoming_texts[:3],
        )

        # 8. Acción Comercial Sugerida
        accion_sugerida, msg_wa = _generate_suggested_commercial_action(
            client_name=client_name,
            product=producto_principal,
            intents=detected_intents,
            crops=detected_crops,
            objections=detected_objections,
        )

        # Enlace wa.me
        clean_tel_digits = re.sub(r"\D", "", phone)
        if clean_tel_digits and not clean_tel_digits.startswith("54"):
            clean_tel_digits = f"549{clean_tel_digits}"
        wa_url = f"https://wa.me/{clean_tel_digits}?text={urllib.parse.quote(msg_wa)}"

        records.append({
            "Telefono": phone,
            "Cliente": client_name,
            "Campana_Origen": campana,
            "Producto_Principal": producto_principal,
            "Productos_Detectados": detected_products,
            "Intencion_Principal": intencion_principal,
            "Intenciones_Detectadas": detected_intents,
            "Que_Pide_El_Cliente": resumen_que_pide,
            "Cultivo_Aplicacion": cultivo_str,
            "Objeciones": objecion_str,
            "Temperatura": temperatura,
            "Total_Mensajes": len(m_list_sorted),
            "Mensajes_Entrantes": len(incoming_texts),
            "Mensajes_Salientes": len(m_list_sorted) - len(incoming_texts),
            "Fecha_Primer_Mensaje": first_date,
            "Fecha_Ultimo_Mensaje": last_date,
            "Fecha_Ultimo_Str": last_date.strftime("%Y-%m-%d %H:%M") if pd.notna(last_date) else "-",
            "Mes_Ultimo": last_date.strftime("%Y-%m") if pd.notna(last_date) else "-",
            "Accion_Sugerida": accion_sugerida,
            "Respuesta_WA_Sugerida": msg_wa,
            "WhatsApp_Link": wa_url,
            "Provincia": crm_lead.get("Provincia", "No identificada"),
            "Localidad": crm_lead.get("Localidad", "-"),
            "Region": crm_lead.get("Region", "-"),
            "Historial_Mensajes": [
                {
                    "is_from_me": bool(m.get("is_from_me") or m.get("fromMe")),
                    "text": str(m.get("text", "")).strip(),
                    "timestamp": str(m.get("timestamp", ""))[:19].replace("T", " "),
                    "name": m.get("name", ""),
                }
                for m in m_list_sorted
                if m.get("text")
            ],
        })

    df_out = pd.DataFrame(records)
    if not df_out.empty:
        for col in ["Fecha_Primer_Mensaje", "Fecha_Ultimo_Mensaje"]:
            if col in df_out.columns:
                df_out[col] = pd.to_datetime(df_out[col], errors="coerce")
                if hasattr(df_out[col].dt, "tz") and df_out[col].dt.tz is not None:
                    df_out[col] = df_out[col].dt.tz_localize(None)
        df_out = df_out.sort_values(by="Fecha_Ultimo_Mensaje", ascending=False).reset_index(drop=True)
    return df_out


def _generate_ai_demand_summary(
    client_name: str,
    product: str,
    intents: List[str],
    crops: List[str],
    objections: List[str],
    incoming_sample: List[str],
) -> str:
    """Genera una síntesis en lenguaje natural de qué solicita exactamente el cliente."""
    req_parts = []
    if any("Presupuesto" in i for i in intents):
        req_parts.append("solicita cotización formal y precios")
    if any("Catálogo" in i for i in intents):
        req_parts.append("pide folleto técnico y especificaciones en PDF")
    if any("Asesoramiento" in i for i in intents):
        req_parts.append("consulta por factibilidad técnica y alcance")
    if any("Stock" in i for i in intents):
        req_parts.append("requiere disponibilidad de stock y plazos de entrega")
    if any("Reunión" in i for i in intents):
        req_parts.append("pide coordinar reunión virtual (Meet) o llamada")
    if any("Financiación" in i for i in intents):
        req_parts.append("consulta opciones de pago y financiación")

    base = f"Interesado en {product}"
    if crops:
        base += f" para cultivo de {', '.join(crops)}"
    if req_parts:
        base += f"; {', '.join(req_parts)}."
    else:
        base += "; consulta general sobre el producto."

    if objections:
        base += f" (Señal de objeción: {', '.join(objections)})."

    return base


def _generate_suggested_commercial_action(
    client_name: str,
    product: str,
    intents: List[str],
    crops: List[str],
    objections: List[str],
) -> Tuple[str, str]:
    """Retorna (Acción comercial resumida, Texto pre-redactado para WhatsApp)."""
    clean_name = client_name.split()[0] if client_name else "Estimado/a"

    if any("Reunión" in i for i in intents):
        accion = "📅 Enviar link de Google Meet y confirmar horario"
        msg = f"¡Hola {clean_name}! ¿Cómo estás? Te escribo para coordinar la reunión por Google Meet sobre {product}. ¿Te queda cómodo que nos conectemos hoy a las 16 hs o mañana por la mañana?"
    elif any("Presupuesto" in i for i in intents):
        accion = "💰 Despachar presupuesto formal y consultar lote/hectáreas"
        msg = f"¡Hola {clean_name}! ¿Cómo estás? Te paso el presupuesto actualizado de {product}. ¿Pudiste definir la cantidad de equipos o hectáreas para ajustar la cotización con bonificación por volumen?"
    elif any("Catálogo" in i for i in intents):
        accion = "📄 Enviar ficha técnica en PDF y consultar cultivo"
        msg = f"¡Hola {clean_name}! Te adjunto la ficha técnica completa y manual de {product}. ¿Para qué tipo de cultivo o campo lo están evaluando?"
    elif any("Financiación" in i for i in intents):
        accion = "💳 Ofrecer esquema en cheques de pago diferido (E-cheq)"
        msg = f"¡Hola {clean_name}! Respecto a las formas de pago de {product}, disponemos de esquemas con valores/cheques diferidos y descuento especial por pago contado. ¿Qué plazo de financiación precisan?"
    else:
        accion = "📲 Recontactar con pitch técnico actualizado"
        msg = f"¡Hola {clean_name}! ¿Cómo estás? Te contacto del equipo técnico de Abatech para saber si pudiste avanzar con el proyecto de {product} o si precisas que revisemos los detalles juntos."

    return accion, msg
