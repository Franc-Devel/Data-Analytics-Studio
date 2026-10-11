"""
Nexo Analytics - Módulo de Inteligencia Artificial (API LLM & Coequiper Comercial)
Provee capacidades de PLN, extracción estructurada de intenciones, auditoría y control
de documentos comerciales (facturas, presupuestos, remitos), relevamiento de WhatsApp
y copiloto comercial utilizando APIs de LLM de alta eficiencia y bajo costo de tokens.
"""

from __future__ import annotations

import base64
import datetime
import json
import mimetypes
import os
import re
import time
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("ai_service")

# Cache de disponibilidad de API LLM (TTL de 10 segundos)
_AI_STATUS_CACHE: Dict[str, Any] = {
    "checked_at": 0.0,
    "available": False,
    "provider": "API LLM (OpenAI / Compatible)",
    "current_model": "",
    "error": "",
    "last_error": "",
}
_CACHE_TTL_SECONDS = 10.0
_LAST_LLM_ERROR: str = ""


@dataclass
class LeadMessageAnalysis:
    """Estructura normalizada para el relevamiento de mensajes de WhatsApp por IA."""
    raw_text: str
    client_name: Optional[str] = None
    locality: Optional[str] = None
    province: Optional[str] = None
    product_line: str = "General"  # Sentek, Davis, Jardineria, Raphael, GSI, General
    intent: str = "Consulta General"  # Presupuesto, Consulta Tecnica, Reclamo, Compra, Seguimiento, Descarte, General
    what_is_requesting: str = ""  # Qué solicita específicamente el cliente
    origin_location: str = ""  # De dónde viene o advertencia de lugar no informado
    missing_info: List[str] = field(default_factory=list)  # Ej: ["⚠️ Cliente no informó lugar de procedencia"]
    temperature: str = "WARM"  # HOT, WARM, COLD
    urgency: str = "MEDIA"  # ALTA, MEDIA, BAJA
    objections: Optional[str] = None
    executive_summary: str = ""
    recommended_action: str = ""
    suggested_closer: Optional[str] = None  # Jony, Luisa, Sergio/Alon
    derivation_summary: str = ""  # Resumen de derivación
    confidence_score: float = 0.85
    is_ai_generated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_ai_status(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Verifica el estado del servicio de API LLM (OpenAI / REST compatible).
    Implementa caché en memoria para no penalizar la latencia de renderizado.
    """
    global _AI_STATUS_CACHE
    cfg = get_config()

    if not cfg.llm_enabled:
        return {
            "enabled": False,
            "available": False,
            "provider": cfg.llm_provider_name,
            "current_model": cfg.llm_model,
            "models": [cfg.llm_model],
            "fallback_model": cfg.llm_model,
            "base_url": cfg.llm_base_url,
            "api_key_configured": False,
            "error": "IA deshabilitada por configuración (LLM_ENABLED=false)",
        }

    now = time.time()
    if not force_refresh and (now - _AI_STATUS_CACHE.get("checked_at", 0)) < _CACHE_TTL_SECONDS:
        return _AI_STATUS_CACHE

    has_key = bool(cfg.llm_api_key and cfg.llm_api_key.strip())
    error_msg = "" if has_key else "Falta configurar OPENAI_API_KEY en .env"

    _AI_STATUS_CACHE = {
        "checked_at": now,
        "enabled": True,
        "available": has_key,
        "provider": cfg.llm_provider_name,
        "current_model": cfg.llm_model,
        "models": [cfg.llm_model],
        "fallback_model": cfg.llm_model,
        "base_url": cfg.llm_base_url,
        "api_key_configured": has_key,
        "error": error_msg,
        "last_error": _LAST_LLM_ERROR,
    }

    return _AI_STATUS_CACHE



def is_ai_available() -> bool:
    """Retorna True si el servicio de LLM API está habilitado y cuenta con API key configurada."""
    return bool(get_ai_status().get("available", False))


def _call_llm(
    prompt: str | List[Dict[str, Any]],
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    json_format: bool = False,
    temperature: float = 0.1,
    timeout: Optional[int] = None,
) -> Optional[str | Dict[str, Any]]:
    """
    Envía una petición de inferencia a la API LLM estándar (OpenAI Chat Completions / REST compatible).
    Optimizado para mínimo consumo de tokens y alta velocidad.
    Soporta llamadas con texto simple o contenido multimodal (imágenes con base64).
    """
    cfg = get_config()
    if not cfg.llm_enabled:
        return None

    api_key = cfg.llm_api_key
    base_url = cfg.llm_base_url.rstrip("/")
    target_model = model or cfg.llm_model
    effective_timeout = timeout or cfg.llm_timeout_seconds

    # Auto-conmutación a modelo de visión si se envían imágenes a Groq
    if isinstance(prompt, list) and any(isinstance(item, dict) and item.get("type") == "image_url" for item in prompt):
        if "groq.com" in base_url and "vision" not in target_model.lower():
            target_model = "llama-3.2-11b-vision-preview"

    # Determinar endpoint de chat completions
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if isinstance(prompt, list):
        messages.append({"role": "user", "content": prompt})
    else:
        messages.append({"role": "user", "content": str(prompt)})

    payload: Dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_format:
        payload["response_format"] = {"type": "json_object"}

    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexoAnalytics/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    global _LAST_LLM_ERROR
    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=effective_timeout,
        )
        if resp.status_code == 200:
            _LAST_LLM_ERROR = ""
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            msg_obj = choices[0].get("message", {})
            raw_res = msg_obj.get("content", "")
            if not raw_res:
                raw_res = msg_obj.get("reasoning", "")
            if json_format:
                try:
                    return json.loads(raw_res)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", raw_res, re.DOTALL)
                    if match:
                        return json.loads(match.group(0))
                    logger.warning(f"Respuesta de LLM API ({target_model}) no es JSON válido: {raw_res[:200]}")
                    return None
            return raw_res
        else:
            provider = cfg.llm_provider_name
            if resp.status_code == 429:
                _LAST_LLM_ERROR = f"Límite de cuota o saldo alcanzado en {provider} (HTTP 429). Por favor verifique sus créditos."
            elif resp.status_code == 401:
                _LAST_LLM_ERROR = f"Clave de API en {provider} no autorizada o inválida (HTTP 401)."
            else:
                _LAST_LLM_ERROR = f"Error HTTP {resp.status_code} en {provider}: {resp.text[:100]}"
            logger.warning(f"Error HTTP {resp.status_code} en LLM API ({target_model}): {resp.text[:150]}")
            return None
    except requests.exceptions.RequestException as e:
        _LAST_LLM_ERROR = f"Fallo de conexión con LLM API: {e}"
        logger.warning(f"Fallo de conexión con LLM API ({target_model}): {e}")
        return None


# Alias de compatibilidad hacia atrás para pruebas y llamadas existentes
_call_ollama = _call_llm



def _heuristic_fallback_analysis(
    text: str,
    sender_name: str = "",
    sender_phone: str = "",
) -> LeadMessageAnalysis:
    """
    Análisis de contingencia basado en reglas cuando la API LLM no se encuentra configurada o disponible.
    Garantiza que la plataforma siga funcionando sin degradación crítica.
    """
    from finance_app.whatsapp_service import detect_product_line, detect_closer_derivation
    from finance_app.lead_intelligence import extract_intent_tags

    p_line = detect_product_line(text)
    is_der, der_target = detect_closer_derivation(text)
    tags = extract_intent_tags(text)

    # Detección simple de temperatura
    t = text.lower()
    if any(k in t for k in ["urgente", "ya", "hoy", "comprar", "transferencia", "cerrar", "cuanto sale"]):
        temperature = "HOT"
        urgency = "ALTA"
    elif any(k in t for k in ["no me interesa", "descartar", "muy caro", "spam"]):
        temperature = "COLD"
        urgency = "BAJA"
    else:
        temperature = "WARM"
        urgency = "MEDIA"

    # Mapeo de closer
    closer = None
    if "jony" in der_target.lower():
        closer = "Jony"
    elif "luisa" in der_target.lower():
        closer = "Luisa"
    elif "sergio" in der_target.lower() or "alon" in der_target.lower():
        closer = "Sergio/Alon"

    clean_summary = text.strip().replace("\n", " ")
    if len(clean_summary) > 120:
        clean_summary = clean_summary[:117] + "..."

    # Relevamiento de datos faltantes y procedencia
    missing_info = ["⚠️ Este cliente no informó lugar / localidad de procedencia"]
    origin_loc = "Lugar no informado"
    what_req = f"Consulta sobre {p_line}" if p_line != "General" else "Consulta general"

    derivation_msg = f"Derivar a {closer or 'Comercial'} para atender {what_req} (⚠️ Avisar: cliente no informó lugar)."

    return LeadMessageAnalysis(
        raw_text=text,
        client_name=sender_name or None,
        locality=None,
        province=None,
        product_line=p_line,
        intent=tags[0] if tags else "Consulta General",
        what_is_requesting=what_req,
        origin_location=origin_loc,
        missing_info=missing_info,
        temperature=temperature,
        urgency=urgency,
        objections=None,
        executive_summary=clean_summary,
        recommended_action="Contactar al cliente para evaluar requerimientos técnicos y confirmar localidad.",
        suggested_closer=closer,
        derivation_summary=derivation_msg,
        confidence_score=0.5,
        is_ai_generated=False,
    )


def analyze_whatsapp_message(
    text: str,
    sender_name: str = "",
    sender_phone: str = "",
    context: Optional[str] = None,
) -> LeadMessageAnalysis:
    """
    Analiza un mensaje de WhatsApp entrante mediante la API de LLM.
    Extrae qué está pidiendo, procedencia (de dónde viene), detecta alertas si falta el lugar,
    clasifica producto, intención, temperatura de compra y genera derivación a closers.
    Optimizado para mínimo consumo de tokens.
    """
    if not text or not str(text).strip():
        return _heuristic_fallback_analysis("", sender_name, sender_phone)

    system_prompt = (
        "Eres el Analista Comercial de IA para Abatech (Nexo Analytics) en Argentina. "
        "Tu objetivo es interpretar mensajes de WhatsApp entrantes con concisión extrema para ahorrar tokens.\n"
        "Líneas de producto:\n"
        "- Sentek: Sondas de humedad de suelo y telemetría.\n"
        "- Davis: Estaciones meteorológicas Vantage Pro2/Vue.\n"
        "- Jardineria: Riego automático parques, programadores Galcon 9001BT.\n"
        "- Raphael: Válvulas hidráulicas de control.\n"
        "- GSI: Silos y secadoras de granos.\n"
        "Closers comerciales:\n"
        "- Jony: Sentek, GSI y cierres complejos.\n"
        "- Luisa: Estaciones Davis y cotizaciones técnicas.\n"
        "- Sergio/Alon: Válvulas Raphael, riego y cuentas Cuyo/NOA.\n"
        "Responde estrictamente un JSON válido."
    )

    prompt = f"""
Interpreta este mensaje de WhatsApp y responde EXCLUSIVAMENTE este JSON:
{{
  "nombre": string o null,
  "localidad": string o null,
  "provincia": string o null,
  "producto_interes": "Sentek" | "Davis" | "Jardineria" | "Raphael" | "GSI" | "General",
  "que_esta_pidiendo": string (resumen de 1 frase: exactamente qué pide el cliente),
  "intencion": "Presupuesto" | "Consulta Tecnica" | "Reclamo" | "Compra" | "Seguimiento" | "Descarte" | "Consulta General",
  "temperatura": "HOT" | "WARM" | "COLD",
  "urgencia": "ALTA" | "MEDIA" | "BAJA",
  "objeciones": string o null,
  "resumen_ejecutivo": string (1 o 2 oraciones),
  "accion_recomendada": string,
  "closer_sugerido": "Jony" | "Luisa" | "Sergio/Alon" | null,
  "datos_faltantes": list of strings (ej: advertir si no informó lugar o contacto)
}}

Remitente: {sender_name or 'No informado'} | Teléfono: {sender_phone or 'No informado'}
{f'Contexto: {context}' if context else ''}
Mensaje:
\"\"\"{text.strip()}\"\"\"
"""

    result = _call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        json_format=True,
        temperature=0.1,
    )

    if not isinstance(result, dict):
        logger.info("LLM API no respondió o no está configurada. Aplicando análisis heurístico de respaldo.")
        return _heuristic_fallback_analysis(text, sender_name, sender_phone)

    try:
        prod = str(result.get("producto_interes", "General")).strip()
        valid_prods = {"Sentek", "Davis", "Jardineria", "Raphael", "GSI", "General"}
        if prod not in valid_prods:
            prod = "General"

        temp = str(result.get("temperatura", "WARM")).upper().strip()
        if temp not in ("HOT", "WARM", "COLD"):
            temp = "WARM"

        urg = str(result.get("urgencia", "MEDIA")).upper().strip()
        if urg not in ("ALTA", "MEDIA", "BAJA"):
            urg = "MEDIA"

        closer = result.get("closer_sugerido")
        if closer and not any(c in str(closer) for c in ["Jony", "Luisa", "Sergio", "Alon"]):
            closer = None

        loc = result.get("localidad")
        prov = result.get("provincia")
        what_req = result.get("que_esta_pidiendo") or f"Consulta por línea {prod}"

        missing_info: List[str] = list(result.get("datos_faltantes") or [])
        if not loc:
            alert_loc = "⚠️ Este cliente no informó lugar / localidad de procedencia"
            if alert_loc not in missing_info:
                missing_info.append(alert_loc)
            origin_loc = "Lugar no informado"
            derivation = f"Derivar a {closer or 'Comercial'} para {what_req} (⚠️ Avisar: el cliente no informó lugar de procedencia)."
        else:
            origin_loc = f"{loc}, {prov}" if prov else loc
            derivation = f"Derivar a {closer or 'Comercial'} para atender {what_req}. Procedencia: {origin_loc}."

        return LeadMessageAnalysis(
            raw_text=text,
            client_name=result.get("nombre") or sender_name or None,
            locality=loc or None,
            province=prov or None,
            product_line=prod,
            intent=result.get("intencion") or "Consulta General",
            what_is_requesting=what_req,
            origin_location=origin_loc,
            missing_info=missing_info,
            temperature=temp,
            urgency=urg,
            objections=result.get("objeciones") or None,
            executive_summary=result.get("resumen_ejecutivo") or text[:120],
            recommended_action=result.get("accion_recomendada") or "Contactar al cliente para seguimiento comercial.",
            suggested_closer=closer,
            derivation_summary=derivation,
            confidence_score=0.95,
            is_ai_generated=True,
        )
    except Exception as e:
        logger.error(f"Error procesando salida JSON de LLM: {e}")
        return _heuristic_fallback_analysis(text, sender_name, sender_phone)


# =========================================================================
# AUDITORÍA, PROCESAMIENTO Y CONTROL DE DOCUMENTOS (COEQUIPER IA)
# =========================================================================

def _review_document_calculations(data: Dict[str, Any]) -> List[str]:
    """
    Auditoría estricta de cuentas y coherencia de datos según el modelo de control
    de llm/06-factura.mjs:
    - Cantidad * Precio Unitario == Subtotal por cada ítem.
    - Suma de subtotales de ítems == Importe Neto.
    - Neto + IVA == Total general.
    - Detección de campos obligatorios faltantes (número, fecha, cliente, localidad).
    """
    advertencias: List[str] = []

    def cerca(a: float, b: float) -> bool:
        return abs(float(a or 0.0) - float(b or 0.0)) < 0.05

    items = data.get("items") or []

    for idx, item in enumerate(items, 1):
        desc = item.get("descripcion") or f"Ítem #{idx}"
        try:
            qty = float(item.get("cantidad") or 0.0)
            pu = float(item.get("precio_unitario") or 0.0)
            sub = float(item.get("subtotal") or 0.0)
            if qty > 0 and pu > 0 and sub > 0 and not cerca(qty * pu, sub):
                advertencias.append(
                    f"El subtotal de '{desc}' ({sub:,.2f}) no coincide con cantidad ({qty}) × precio unitario ({pu:,.2f})."
                )
        except (ValueError, TypeError):
            advertencias.append(f"Valores numéricos no válidos en ítem '{desc}'.")

    if items:
        try:
            suma_items = sum(float(i.get("subtotal") or 0.0) for i in items)
            neto = float(data.get("neto") or 0.0)
            if neto > 0 and not cerca(suma_items, neto):
                advertencias.append(
                    f"La suma de los subtotales de ítems ({suma_items:,.2f}) no coincide con el neto ({neto:,.2f})."
                )
        except (ValueError, TypeError):
            pass

    try:
        neto = float(data.get("neto") or 0.0)
        iva = float(data.get("iva") or 0.0)
        total = float(data.get("total") or 0.0)
        if total > 0 and neto > 0 and not cerca(neto + iva, total):
            advertencias.append(
                f"El neto ({neto:,.2f}) más el IVA ({iva:,.2f}) no coincide con el total declarado ({total:,.2f})."
            )
    except (ValueError, TypeError):
        advertencias.append("Inconsistencia en el formato numérico de neto, iva o total.")

    # Control de datos obligatorios para el CRM
    cliente = data.get("cliente") or {}
    if not cliente.get("nombre"):
        advertencias.append("El documento no contiene nombre o razón social del cliente.")
    if not cliente.get("localidad"):
        advertencias.append("El documento no especifica localidad del cliente.")
    if not data.get("numero"):
        advertencias.append("No se detectó número de comprobante o documento.")
    if not data.get("fecha"):
        advertencias.append("No se identificó la fecha de emisión del documento.")

    return advertencias


def process_document_with_ai(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Procesa un documento (imagen JPG/PNG, PDF, Excel o texto) utilizando la API de LLM.
    Extrae entidades, ítems contables, realiza el control matemático completo
    y produce una primera devolución estructurada lista para revisión humana.
    """
    ext = Path(filename).suffix.lower()
    text_content = ""
    image_base64 = None

    # 1. Determinar tipo de archivo y extraer contenido base
    is_image = ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
    if is_image:
        mime = mime_type or mimetypes.guess_type(filename)[0] or "image/jpeg"
        image_base64 = f"data:{mime};base64,{base64.b64encode(file_bytes).decode('utf-8')}"
    elif ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(file_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages[:6]):  # Limitar a las primeras 6 páginas
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"--- Página {i+1} ---\n{txt}")
            text_content = "\n".join(pages_text)
        except Exception as e:
            logger.warning(f"Error extrayendo texto de PDF con pypdf: {e}")
            text_content = f"Archivo PDF {filename} ({len(file_bytes)} bytes)."
    elif ext in (".xlsx", ".xls"):
        try:
            import pandas as pd
            excel_file = BytesIO(file_bytes)
            xl = pd.ExcelFile(excel_file)
            sheets_summary = []
            for sheet_name in xl.sheet_names[:4]:
                df = xl.parse(sheet_name, nrows=30)
                sheets_summary.append(f"--- Hoja: {sheet_name} ---\n{df.to_string(index=False)}")
            text_content = "\n\n".join(sheets_summary)
        except Exception as e:
            logger.warning(f"Error procesando Excel: {e}")
            text_content = f"Archivo Excel {filename} ({len(file_bytes)} bytes)."
    else:
        # Texto plano / CSV
        try:
            text_content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = file_bytes.decode("latin-1", errors="replace")

    # 2. Instrucciones para la API LLM (Extracción y Control)
    instrucciones = """
    Sos un auditor experto de Inteligencia Comercial y Control de Gestión de Nexo Analytics.
    Extraé los datos del documento comercial o comprobante adjunto y devolvé EXCLUSIVAMENTE este JSON:
    {
      "tipo_documento": "Factura A" | "Factura B" | "Factura C" | "Remito" | "Orden de Compra" | "Presupuesto" | "Comprobante de Pago" | "Ficha Técnica" | "Documento Comercial",
      "numero": "0001-00001234" o null,
      "fecha": "AAAA-MM-DD" o null,
      "emisor": { "nombre": string o null, "cuit": string o null, "direccion": string o null },
      "cliente": { "nombre": string o null, "cuit": string o null, "telefono": string o null, "localidad": string o null, "provincia": string o null, "direccion": string o null },
      "items": [
        { "descripcion": string, "cantidad": 0.0, "precio_unitario": 0.0, "subtotal": 0.0 }
      ],
      "neto": 0.0,
      "iva": 0.0,
      "total": 0.0,
      "moneda": "ARS" | "USD",
      "linea_producto": "Sentek" | "Davis" | "Jardineria" | "Raphael" | "GSI" | "General",
      "resumen_ejecutivo": string (síntesis de 2 oraciones del documento)
    }

    Los importes van como números JSON con punto decimal y sin separador de miles.
    Si un dato no aparece o no se puede leer, usá null.
    """

    if is_image and image_base64:
        contenido_prompt: Any = [
            {"type": "text", "text": f"Analiza esta imagen del documento ({filename}) y extrae los datos contables y comerciales."},
            {"type": "image_url", "image_url": {"url": image_base64, "detail": "high"}},
        ]
    else:
        # Truncar texto para optimizar tokens
        safe_text = text_content[:6000] if text_content else f"Documento: {filename}"
        contenido_prompt = (
            f"Analiza el siguiente documento ({filename}) y extrae sus datos:\n\n"
            f"```text\n{safe_text}\n```"
        )

    res = _call_llm(
        prompt=contenido_prompt,
        system_prompt=instrucciones,
        json_format=True,
        temperature=0.1,
    )

    is_ai = isinstance(res, dict)
    if not is_ai:
        # Fallback heurístico si no hay API disponible
        logger.info(f"API no disponible, generando lectura preliminar para {filename}")
        data = {
            "tipo_documento": "Documento Comercial",
            "numero": "S/N",
            "fecha": datetime.date.today().isoformat(),
            "emisor": {"nombre": "Emisor no detectado", "cuit": None, "direccion": None},
            "cliente": {"nombre": f"Cliente de {filename}", "cuit": None, "telefono": None, "localidad": None, "provincia": None},
            "items": [{"descripcion": f"Contenido analizado de {filename}", "cantidad": 1.0, "precio_unitario": 0.0, "subtotal": 0.0}],
            "neto": 0.0,
            "iva": 0.0,
            "total": 0.0,
            "moneda": "ARS",
            "linea_producto": "General",
            "resumen_ejecutivo": f"Documento {filename} procesado preliminarmente en modo contingencia.",
        }
    else:
        data = res  # type: ignore

    # 3. Control y auditoría estricta de cálculos
    advertencias = _review_document_calculations(data)
    cuentas_cierran = len(advertencias) == 0

    devolucion = {
        "titulo": f"{data.get('tipo_documento', 'Documento')} {data.get('numero') or ''}".strip(),
        "resumen": data.get("resumen_ejecutivo") or "Documento procesado.",
        "emisor": data.get("emisor") or {},
        "cliente": data.get("cliente") or {},
        "items": data.get("items") or [],
        "neto": float(data.get("neto") or 0.0),
        "iva": float(data.get("iva") or 0.0),
        "total": float(data.get("total") or 0.0),
        "moneda": data.get("moneda") or "ARS",
        "linea_producto": data.get("linea_producto") or "General",
        "cuentas_cierran": cuentas_cierran,
        "advertencias": advertencias,
        "mensaje_control": (
            "✅ Las cuentas cierran. Todo verificado correctamente."
            if cuentas_cierran
            else f"⚠️ Se detectaron {len(advertencias)} observaciones o inconsistencias numéricas."
        ),
    }

    return {
        "filename": filename,
        "is_ai_generated": is_ai,
        "datos": data,
        "advertencias": advertencias,
        "cuentas_cierran": cuentas_cierran,
        "primera_devolucion": devolucion,
    }


def save_document_to_database(
    doc_result: Dict[str, Any],
    user_actor: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Suma la información del documento comercial aceptado a la base de datos del proyecto:
    1. Crea o actualiza el Cliente en la tabla de Customers (con localidad, provincia, etc.).
    2. Registra la Oportunidad comercial / Transacción con su monto e ítems.
    3. Registra una entrada en el Historial de Actividad (ActivityLog).
    4. Emite un evento inmutable en el AuditLog.
    """
    from finance_app.db.session import get_db_session
    from finance_app.db.crm_service import create_or_update_customer, create_opportunity
    from finance_app.db.models import ActivityLog

    datos = doc_result.get("datos", {})
    cli_dict = datos.get("cliente") or {}
    filename = doc_result.get("filename", "documento")

    # Extraer campos de cliente
    raw_name = (cli_dict.get("nombre") or "").strip()
    if not raw_name:
        raw_name = f"Cliente Ref {filename}"

    raw_phone = (cli_dict.get("telefono") or "").strip()
    if not raw_phone:
        # Teléfono sintético único determinístico si el documento no lo contiene
        raw_phone = f"+54 9 11 {abs(hash(raw_name)) % 10000000:07d}"

    locality = cli_dict.get("localidad")
    province = cli_dict.get("provincia")
    product_line = datos.get("linea_producto") or "General"
    total_amount = float(datos.get("total") or 0.0)
    tipo_doc = datos.get("tipo_documento") or "Documento"
    numero_doc = datos.get("numero") or "S/N"

    with get_db_session() as session:
        # 1. Crear o actualizar cliente
        customer, created = create_or_update_customer(
            session=session,
            phone=raw_phone,
            full_name=raw_name,
            product_line=product_line,
            province=province,
            locality=locality,
            lead_score=80 if total_amount > 0 else 60,
            segment="HOT" if total_amount > 0 else "WARM",
            status="CALIFICADO",
            company=cli_dict.get("cuit"),
            notes=f"Incorporado por Coequiper IA desde documento {filename} ({tipo_doc} {numero_doc}).",
            user_actor=user_actor,
        )

        # 2. Registrar Oportunidad Comercial si hay monto asociado
        opp_stage = "CERRADO_GANADO" if "Factura" in tipo_doc or "Pago" in tipo_doc else "COTIZADO"
        opp = create_opportunity(
            session=session,
            customer_id=customer.id,
            title=f"{tipo_doc} #{numero_doc} ({product_line})",
            product=product_line,
            amount_ars=total_amount,
            stage=opp_stage,
            probability_pct=100 if opp_stage == "CERRADO_GANADO" else 75,
            notes=f"Documento analizado y verificado por IA. Ítems: {len(datos.get('items', []))}. Total: ${total_amount:,.2f}.",
            user_actor=user_actor,
        )

        # 3. Registrar Log de Actividad
        act = ActivityLog(
            customer_id=customer.id,
            channel="DOCUMENT_IA",
            direction="INBOUND",
            summary=f"Coequiper IA procesó {tipo_doc} {numero_doc} (${total_amount:,.2f})",
            content=datos.get("resumen_ejecutivo") or f"Documento {filename} incorporado a base de datos.",
            metadata_json=json.dumps({
                "filename": filename,
                "tipo_documento": tipo_doc,
                "numero": numero_doc,
                "total": total_amount,
                "items": datos.get("items", []),
                "advertencias": doc_result.get("advertencias", []),
            }),
        )
        session.add(act)
        session.flush()

        logger.info(f"Documento {filename} incorporado a base de datos: Customer ID={customer.id}, Opportunity ID={opp.id}")

        return {
            "success": True,
            "customer_id": customer.id,
            "customer_name": raw_name,
            "opportunity_id": opp.id,
            "opportunity_title": opp.title,
            "total_amount": total_amount,
            "created_customer": created,
            "message": f"Se incorporó con éxito {tipo_doc} #{numero_doc} a la base de datos (Cliente: {raw_name}).",
        }


# =========================================================================
# ASISTENTE DE CONSULTAS Y COPILOTO DE DATOS
# =========================================================================

def ask_crm_assistant(
    question: str,
    crm_summary_context: Dict[str, Any],
) -> str:
    """
    Copiloto de análisis de datos y consultoría comercial en lenguaje natural.
    Responde consultas ejecutivas sobre los KPIs del CRM, tasas de conversión y recomendaciones.
    """
    if not is_ai_available():
        return (
            "⚠️ El motor de Inteligencia Artificial no se encuentra disponible o configurado en este momento. "
            "Asegúrate de definir `OPENAI_API_KEY` en tu archivo `.env`."
        )

    context_str = json.dumps(crm_summary_context, indent=2, ensure_ascii=False)

    system_prompt = (
        "Eres el Asistente Senior de Inteligencia Comercial y Data Science de Nexo Analytics. "
        "Tu objetivo es brindar respuestas ejecutivas, analíticas y basadas estrictamente "
        "en los datos provistos del CRM y las campañas publicitarias. Comunica en español profesional y conciso."
    )

    prompt = f"""
Contexto de métricas y datos del CRM:
```json
{context_str}
```

Pregunta del analista o gerente comercial:
"{question}"

Responde de forma concisa, destacando hallazgos clave, alertas y recomendaciones tácticas accionables.
"""

    res = _call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.2,
    )

    if isinstance(res, str) and res.strip():
        return res.strip()

    return "No fue posible procesar la consulta en este momento. Por favor reintente."


def analyze_conversation_history(
    messages: List[Dict[str, Any]],
    client_name: str = "",
) -> Dict[str, Any]:
    """
    Analiza una secuencia completa de mensajes entre el cliente y la empresa.
    Produce una auditoría 360° del estado de la negociación.
    """
    if not messages:
        return {
            "summary": "Sin mensajes registrados para analizar.",
            "temperature": "COLD",
            "key_topics": [],
            "pending_issues": [],
            "next_step": "Iniciar primer contacto.",
        }

    formatted_thread = []
    for m in messages[-20:]:
        sender = "Empresa" if m.get("is_from_me") else (m.get("sender_name") or client_name or "Cliente")
        content = m.get("text", m.get("message", m.get("summary", "")))
        formatted_thread.append(f"{sender}: {content}")

    thread_text = "\n".join(formatted_thread)

    prompt = f"""
Analiza la siguiente conversación de WhatsApp entre un cliente ({client_name or 'Cliente'}) y la empresa Abatech.
Devuelve EXCLUSIVAMENTE un JSON con:
{{
  "resumen_general": string (resumen ejecutivo de la relación y estado actual del negocio),
  "temperatura_general": "HOT" | "WARM" | "COLD",
  "temas_clave": list of strings (productos, requerimientos o inquietudes principales),
  "objeciones_o_pendientes": list of strings (dudas no resueltas, trabas de precio, demoras),
  "estrategia_sugerida": string (estrategia comercial recomendada para el closer)
}}

Conversación:
\"\"\"
{thread_text}
\"\"\"
"""

    res = _call_llm(
        prompt=prompt,
        json_format=True,
        temperature=0.1,
    )

    if isinstance(res, dict):
        return {
            "summary": res.get("resumen_general", "Conversación en curso."),
            "temperature": res.get("temperatura_general", "WARM"),
            "key_topics": res.get("temas_clave", []),
            "pending_issues": res.get("objeciones_o_pendientes", []),
            "next_step": res.get("estrategia_sugerida", "Realizar llamada de seguimiento."),
            "is_ai": True,
        }

    return {
        "summary": f"Historial con {len(messages)} mensajes registrados.",
        "temperature": "WARM",
        "key_topics": ["Seguimiento general"],
        "pending_issues": [],
        "next_step": "Revisar últimos mensajes y coordinar recontacto.",
        "is_ai": False,
    }


# =========================================================================
# MOTOR COGNITIVO AUTÓNOMO (LIGHTFIELD CRM / PROACTIVE PROPOSALS)
# =========================================================================
def run_lightfield_analysis(
    history: List[Dict[str, Any]],
    context_chunks: Optional[List[str]] = None,
    client_name: str = "",
    current_stage: str = "NUEVO",
) -> Dict[str, Any]:
    """
    Ejecuta una auditoría cognitiva completa sobre las interacciones de un cliente.
    Infiere avances de etapa, compromisos/tareas y factores de riesgo para someterlos
    a validación humana (Human-in-the-Loop) sin alterar la base de datos a ciegas.
    """
    if not history:
        return {
            "analysis": {},
            "proposals": [],
            "is_ai": False,
        }

    formatted_thread = []
    for m in history[-25:]:
        sender = "VENDEDOR" if m.get("is_from_me") or str(m.get("direction", "")).upper() == "OUTBOUND" else (m.get("sender_name") or client_name or "CLIENTE")
        content = m.get("text") or m.get("content") or m.get("summary") or ""
        if content:
            formatted_thread.append(f"{sender}: {content}")

    thread_text = "\n".join(formatted_thread)
    context_text = "\n---\n".join(context_chunks) if context_chunks else ""

    prompt = f"""
Analiza la siguiente conversación de WhatsApp entre el cliente ({client_name or 'Cliente'}) y el equipo comercial de Abatech (Nexo Analytics).
Etapa comercial actual registrada en el CRM: "{current_stage}".

Debes responder EXCLUSIVAMENTE un JSON válido con la siguiente estructura estricta:
{{
  "client_intent": string (intención general del cliente),
  "detected_commitments": [
    {{
      "promiser": "VENDEDOR" | "CLIENTE",
      "action": string (acción concreta comprometida o requerida),
      "deadline_hint": string o null (plazo mencionado, ej: 'antes del viernes', 'mañana'),
      "evidence_quote": string (cita textual exacta del mensaje donde surge el compromiso)
    }}
  ],
  "deal_risk_factors": [
    {{
      "risk_type": string (ej: 'Objeción de Costo', 'Demora de Entrega', 'Competencia', 'Falta de Respuesta'),
      "detail": string (explicación breve del riesgo comercial),
      "evidence_quote": string (cita textual exacta donde se evidencia el riesgo)
    }}
  ],
  "suggested_stage": "NUEVO" | "EN_SEGUIMIENTO" | "CALIFICADO" | "COTIZADO" | "GANADO" | "PERDIDO" | "DESCARTADO",
  "suggested_closer": "Jony" | "Luisa" | "Sergio/Alon" | null,
  "confidence": float (entre 0.0 y 1.0)
}}

{f'Fragmentos de contexto semántico previo:\n{context_text}\n' if context_text else ''}
Conversación reciente:
\"\"\"
{thread_text}
\"\"\"
"""

    res = _call_llm(
        prompt=prompt,
        json_format=True,
        temperature=0.15,
    )

    if not isinstance(res, dict):
        logger.info("LLM API no disponible para Lightfield analysis, ejecutando heurística de respaldo.")
        return _lightfield_fallback_analysis(history, current_stage)

    # Transformar a propuestas estructuradas para el UI
    proposals = []
    confidence = float(res.get("confidence", 0.9))

    suggested_stage = str(res.get("suggested_stage", current_stage)).upper().strip()
    valid_stages = {"NUEVO", "EN_SEGUIMIENTO", "CALIFICADO", "COTIZADO", "GANADO", "PERDIDO", "DESCARTADO"}
    if suggested_stage in valid_stages and suggested_stage != current_stage.upper().strip():
        evidence = res.get("client_intent", "")
        if res.get("detected_commitments"):
            evidence = res["detected_commitments"][0].get("evidence_quote") or evidence
        proposals.append({
            "id": f"p_stage_{abs(hash(suggested_stage + str(confidence))) % 100000}",
            "type": "STAGE_UPDATE",
            "title": f"Avance de Etapa Sugerido: {suggested_stage}",
            "description": f"Se infiere transición de '{current_stage}' a '{suggested_stage}' según la evolución de la charla.",
            "evidence": evidence or f"Intención: {res.get('client_intent')}",
            "suggested_value": suggested_stage,
            "current_value": current_stage,
            "confidence": confidence,
            "rationale": f"Intención detectada: {res.get('client_intent')}. Closer recomendado: {res.get('suggested_closer', 'N/A')}.",
        })

    for idx, c in enumerate(res.get("detected_commitments", [])):
        action = c.get("action", "").strip()
        if action:
            deadline = f"Plazo: {c.get('deadline_hint')}" if c.get("deadline_hint") else "Sin plazo explícito"
            promiser = c.get("promiser", "VENDEDOR")
            proposals.append({
                "id": f"p_task_{abs(hash(action + str(idx))) % 100000}",
                "type": "COMMITMENT_TASK",
                "title": f"Tarea de Seguimiento: {action}",
                "description": f"Compromiso de {promiser} ({deadline}).",
                "evidence": c.get("evidence_quote", action),
                "suggested_value": action,
                "current_value": None,
                "confidence": confidence,
                "rationale": f"Compromiso asumido por {promiser}. {deadline}.",
            })

    for idx, r in enumerate(res.get("deal_risk_factors", [])):
        risk_type = r.get("risk_type", "Alerta Comercial").strip()
        detail = r.get("detail", "").strip()
        proposals.append({
            "id": f"p_risk_{abs(hash(risk_type + str(idx))) % 100000}",
            "type": "DEAL_RISK",
            "title": f"Riesgo Comercial: {risk_type}",
            "description": detail or "Factor de riesgo detectado en la conversación.",
            "evidence": r.get("evidence_quote", detail),
            "suggested_value": risk_type,
            "current_value": None,
            "confidence": confidence,
            "rationale": detail,
        })

    return {
        "analysis": res,
        "proposals": proposals,
        "is_ai": True,
    }


def _lightfield_fallback_analysis(history: List[Dict[str, Any]], current_stage: str) -> Dict[str, Any]:
    """Heurística de contingencia para propuestas cuando la IA no responde."""
    full_text = " ".join([m.get("text") or m.get("content") or m.get("summary") or "" for m in history]).lower()
    proposals = []

    if any(k in full_text for k in ["presupuest", "cotiz", "precio", "cuanto sale"]) and current_stage not in ("COTIZADO", "GANADO"):
        proposals.append({
            "id": f"fb_stage_{abs(hash(full_text[:20])) % 100000}",
            "type": "STAGE_UPDATE",
            "title": "Avance de Etapa Sugerido: COTIZADO",
            "description": "El cliente solicitó cotización o precios en el historial reciente.",
            "evidence": "Solicitud explícita de cotización detectada.",
            "suggested_value": "COTIZADO",
            "current_value": current_stage,
            "confidence": 0.8,
            "rationale": "Detección de solicitud de presupuesto por palabras clave.",
        })
        proposals.append({
            "id": f"fb_task_{abs(hash(full_text[:30])) % 100000}",
            "type": "COMMITMENT_TASK",
            "title": "Tarea de Seguimiento: Enviar cotización solicitada",
            "description": "Enviar propuesta formal de equipos al prospecto.",
            "evidence": "Consulta de precios pendiente de respuesta.",
            "suggested_value": "Enviar cotización formal",
            "current_value": None,
            "confidence": 0.8,
            "rationale": "Compromiso de envío de cotización detectado.",
        })

    if any(k in full_text for k in ["muy caro", "se va de presupuesto", "otra marca", "descartar", "no llego"]):
        proposals.append({
            "id": f"fb_risk_{abs(hash(full_text[:40])) % 100000}",
            "type": "DEAL_RISK",
            "title": "Riesgo Comercial: Objeción de Precio / Presupuesto",
            "description": "El cliente manifestó dudas respecto al costo o presupuesto.",
            "evidence": "Menciones de precio elevado o presupuesto ajustado.",
            "suggested_value": "Objeción de Costo",
            "current_value": None,
            "confidence": 0.75,
            "rationale": "Detección de objeción de presupuesto.",
        })

    return {
        "analysis": {"client_intent": "Consulta Comercial", "suggested_stage": current_stage},
        "proposals": proposals,
        "is_ai": False,
    }
