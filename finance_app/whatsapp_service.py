from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import threading
import time
import tempfile
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from finance_app.lead_intelligence import (
    extract_geo_from_phone,
    calculate_lead_score,
    clean_product_line,
    extract_intent_tags,
    sanitize_display_name,
)
from finance_app.config import get_config
from finance_app.logging_config import get_logger
from finance_app.backup_manager import create_backup

logger = get_logger("whatsapp_service")

_cfg = get_config()
STATE_FILE = _cfg.whatsapp_sync_state_path
CONFIG_FILE = _cfg.whatsapp_config_path
INBOX_DIR = _cfg.whatsapp_inbox_dir
MAX_CONTACT_DATE_COLUMNS = 24
_EXCEL_LOCK = threading.RLock()


def _serialized_excel_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with _EXCEL_LOCK:
            return func(*args, **kwargs)
    return wrapper


def _contact_date_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if str(c).upper().startswith("FECHA CONTACTO")]


def _safe_concat(dfs: List[pd.DataFrame | pd.Series], ignore_index: bool = True, axis: int = 0) -> pd.DataFrame:
    """
    Concatena DataFrames/Series de forma segura descartando objetos vacíos
    y previniendo FutureWarnings de pandas cuando hay columnas all-NA.
    """
    clean_items = []
    for item in dfs:
        if item is None:
            continue
        if isinstance(item, (pd.DataFrame, pd.Series)) and item.empty:
            continue
        clean_items.append(item)
    if not clean_items:
        return pd.DataFrame()
    if len(clean_items) == 1:
        single = clean_items[0]
        return single.copy() if hasattr(single, "copy") else single

    if axis == 1:
        # El constructor alinea Series por índice sin pasar por la ruta de concat
        # que emite FutureWarning al mezclar datetime/timedelta con valores nulos.
        columns = {}
        for position, item in enumerate(clean_items):
            if isinstance(item, pd.Series):
                columns[position] = item
            else:
                for name in item.columns:
                    columns[(position, name)] = item[name]
        return pd.DataFrame(columns)

    # Pandas 3 cambiará la inferencia de dtype cuando un operando contiene una
    # columna enteramente nula. La quitamos sólo durante concat y restauramos
    # después la unión completa de columnas, conservando el esquema esperado.
    all_columns = list(dict.fromkeys(
        column
        for item in clean_items
        if isinstance(item, pd.DataFrame)
        for column in item.columns
    ))
    prepared = []
    for item in clean_items:
        if isinstance(item, pd.DataFrame):
            useful_columns = [column for column in item.columns if not item[column].isna().all()]
            if useful_columns:
                prepared.append(item[useful_columns])
        else:
            prepared.append(item)
    if not prepared:
        return pd.DataFrame(columns=all_columns)
    if ignore_index and all(isinstance(item, pd.DataFrame) for item in prepared):
        # Construcción por registros: evita por completo la inferencia interna
        # de concat que pandas 2.x delega a una unidad timedelta obsoleta.
        records = [record for item in prepared for record in item.to_dict("records")]
        result = pd.DataFrame.from_records(records)
    else:
        result = pd.concat(prepared, ignore_index=ignore_index, axis=0)
    return result.reindex(columns=all_columns) if all_columns else result


def _compact_contact_dates(master: pd.DataFrame) -> pd.DataFrame:
    """Keep a bounded CRM summary; full messages remain in whatsapp_inbox."""
    date_cols = _contact_date_columns(master)
    if not date_cols:
        return master
    parsed = master[date_cols].apply(pd.to_datetime, errors="coerce")
    # Count every populated legacy cell, including malformed date strings;
    # parsing should affect alert dates, never the historical interaction total.
    counts = master[date_cols].notna().sum(axis=1)
    first_dates, last_dates = parsed.min(axis=1), parsed.max(axis=1)
    if "FECHA_PRIMER_CONTACTO_CRM" in master:
        stored_first = pd.to_datetime(master["FECHA_PRIMER_CONTACTO_CRM"], errors="coerce")
        first_dates = _safe_concat([first_dates, stored_first], axis=1).min(axis=1)
    if "FECHA_ULTIMO_CONTACTO_CRM" in master:
        stored_last = pd.to_datetime(master["FECHA_ULTIMO_CONTACTO_CRM"], errors="coerce")
        last_dates = _safe_concat([last_dates, stored_last], axis=1).max(axis=1)
    keep_count = min(MAX_CONTACT_DATE_COLUMNS, max(2, int(counts.clip(upper=MAX_CONTACT_DATE_COLUMNS).max())))
    target_cols = ["FECHA CONTACTO"] + [f"FECHA CONTACTO.{i}" for i in range(1, keep_count)]
    compact = pd.DataFrame(pd.NaT, index=master.index, columns=target_cols)
    for idx in master.index:
        values = sorted(set(parsed.loc[idx].dropna().tolist()))
        if len(values) > keep_count:
            values = [values[0], *values[-(keep_count - 1):]]
        for pos, value in enumerate(values):
            compact.at[idx, target_cols[pos]] = value
    result = master.drop(columns=date_cols).copy()
    insert_at = min(8, len(result.columns))
    for col in reversed(target_cols):
        result.insert(insert_at, col, compact[col])
    existing = pd.to_numeric(result.get("CANT_CONTACTOS_TOTAL"), errors="coerce") if "CANT_CONTACTOS_TOTAL" in result else pd.Series(0, index=result.index)
    result["CANT_CONTACTOS_TOTAL"] = _safe_concat([existing, counts], axis=1).max(axis=1).fillna(0).astype(int)
    result["FECHA_PRIMER_CONTACTO_CRM"] = first_dates
    result["FECHA_ULTIMO_CONTACTO_CRM"] = last_dates
    return result


def _write_excel_atomic(path: Path, workbook: Dict[str, pd.DataFrame]) -> None:
    """Write beside the target and replace it only after the ZIP is complete."""
    import os
    path = path.resolve()
    
    # Auto-backup antes de mutar archivo de producción existente
    if path.exists() and get_config().auto_backup_enabled:
        create_backup(path, tag="pre_whatsapp_sync")
        
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".xlsx", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
            for sheet_name, sheet_df in workbook.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        temp_path.replace(path)
        logger.info(f"Excel de leads actualizado de forma atomica: {path.name}")
    except Exception as e:
        logger.error(f"Error en escritura atomica de Excel {path.name}: {e}", exc_info=True)
        raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _record_contact_date(master: pd.DataFrame, row_idx: Any, value: datetime.datetime) -> None:
    """Record a contact without adding unbounded columns to the workbook."""
    cols = _contact_date_columns(master)
    for col in cols:
        if pd.isna(master.at[row_idx, col]):
            master.at[row_idx, col] = value
            break
    else:
        if not cols:
            master["FECHA CONTACTO"] = pd.NaT
            master.at[row_idx, "FECHA CONTACTO"] = value
        else:
            valid = [(pd.to_datetime(master.at[row_idx, c], errors="coerce"), c) for c in cols]
            valid = [(v, c) for v, c in valid if pd.notna(v)]
            replace_col = min(valid)[1] if valid else cols[0]
            master.at[row_idx, replace_col] = value
    current = pd.to_numeric(master.at[row_idx, "CANT_CONTACTOS_TOTAL"], errors="coerce") if "CANT_CONTACTOS_TOTAL" in master else 0
    master.at[row_idx, "CANT_CONTACTOS_TOTAL"] = int(current) + 1 if pd.notna(current) else 1
    master.at[row_idx, "FECHA_ULTIMO_CONTACTO_CRM"] = value


@dataclass
class WhatsAppMessage:
    message_id: str
    sender_phone: str
    sender_name: str
    timestamp: datetime.datetime
    text: str
    is_from_me: bool = False


@dataclass
class WhatsAppSyncResult:
    new_leads: int = 0
    updated_leads: int = 0
    processed_messages: int = 0
    sync_time: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class WhatsAppSyncState:
    """Maneja la persistencia del estado incremental de sincronización."""

    def __init__(self, state_file: Path = STATE_FILE) -> None:
        self.state_file = state_file
        self.last_sync_iso: str = "2026-01-01T00:00:00"
        self.processed_ids: set[str] = set()
        self.processed_phones: set[str] = set()
        self.total_synced_leads: int = 0
        self.load()

    def load(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_sync_iso = data.get("last_sync_iso", self.last_sync_iso)
                    self.processed_ids = set(data.get("processed_ids", []))
                    self.processed_phones = set(data.get("processed_phones", []))
                    self.total_synced_leads = data.get("total_synced_leads", 0)
            except Exception:
                pass

    def save(self) -> None:
        temp_path = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({
                    "last_sync_iso": self.last_sync_iso,
                    "processed_ids": list(self.processed_ids),
                    "processed_phones": list(self.processed_phones),
                    "total_synced_leads": self.total_synced_leads,
                }, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.state_file)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()

    def is_processed(self, message_id: str) -> bool:
        return message_id in self.processed_ids

    def mark_processed(self, message_id: str, phone: str = "") -> None:
        self.processed_ids.add(message_id)
        if phone:
            self.processed_phones.add(phone)


# =========================================================================
# PARSERS NLP & EXTRACCIÓN DE ENTIDADES
# =========================================================================
def extract_canonical_phone_digits(raw_phone: str) -> str:
    """
    Extrae los dígitos significativos de un teléfono argentino (10 dígitos: código de área + número local).
    Elimina prefijos internacionales (+54, 54, +549, 549), ceros iniciales (0351 -> 351), y prefijo móvil 15.
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if not digits:
        return ""
    # Quitar 549 o 54 si tiene más de 10 dígitos
    if digits.startswith("549") and len(digits) >= 12:
        digits = digits[3:]
    elif digits.startswith("54") and len(digits) >= 11:
        digits = digits[2:]
    # Quitar 0 inicial de código de área (ej: 0351... -> 351...)
    if digits.startswith("0") and len(digits) >= 10:
        digits = digits[1:]
    # Quitar 15 si está al inicio
    if digits.startswith("15") and len(digits) >= 10:
        digits = digits[2:]
    # Quitar 15 intermedio entre código de área y abonado (ej: 381 15 4634094 -> 3814634094)
    if len(digits) >= 11:
        digits = re.sub(r"^(11|2\d{2,3}|3\d{2,3})15(\d{6,8})$", r"\1\2", digits)
    return digits


def normalize_contact_name(name: str) -> str:
    """Normaliza un nombre de contacto para facilitar búsquedas y coincidencias tolerantes."""
    if not name:
        return ""
    n = re.sub(r"[^\w\s]", " ", str(name).lower())
    # Remover títulos/honoríficos y nombres genéricos comunes
    n = re.sub(r"\b(ing|lic|dr|dra|agr|sr|sra|don|dona|abatech|empresa|contacto|cliente|whatsapp|lead|user|usuario)\b", " ", n)
    return " ".join(n.split())


def clean_phone_number(raw_phone: str) -> str:
    """Normaliza un número de teléfono argentino a formato estándar legible."""
    if not raw_phone:
        return ""
    raw_str = str(raw_phone).strip()
    if "@lid" in raw_str:
        return raw_str
    digits = extract_canonical_phone_digits(raw_str)
    if not digits:
        return raw_str

    if len(digits) == 10:
        # Formatear: ej 3512 38-3481 o 11 3215-6510
        if digits.startswith("11"):
            return f"11 {digits[2:6]}-{digits[6:]}"
        return f"{digits[:4]} {digits[4:6]}-{digits[6:]}"
    elif len(digits) == 11:
        return f"{digits[:4]} {digits[4:7]}-{digits[7:]}"
    return digits


def detect_product_line(text: str) -> str:
    """Detecta la línea de producto de interés a partir del texto del mensaje."""
    t = text.lower()
    if any(w in t for w in ["sentek", "sonda", "humedad", "suelo", "capacitiva", "perfil"]):
        return "Sentek"
    if any(w in t for w in ["davis", "estacion", "estación", "meteorologica", "meteorológica", "vantage", "anemometro", "anemómetro", "clima"]):
        return "Davis"
    if any(w in t for w in ["jardin", "jardineria", "jardinería", "riego", "galcon", "goteo", "aspersor", "programador"]):
        return "Jardineria"
    if any(w in t for w in ["raphael", "rafael", "valvula", "válvula", "hidraulica", "hidráulica", "presion", "presión"]):
        return "Raphael"
    if any(w in t for w in ["gsi", "silo", "secadora", "grano", "acopio"]):
        return "GSI"
    return "Sentek"  # Línea principal por defecto


def detect_closer_derivation(text: str) -> Tuple[int, str]:
    """Detecta si el mensaje indica una derivación a un closer comercial."""
    t = text.lower()
    if any(w in t for w in ["jony", "jonathan", "derivado a jony", "pasa a jony"]):
        return 1, "Derivados Jony"
    if any(w in t for w in ["luisa", "derivado a luisa", "pasa a luisa"]):
        return 1, "Derivados Luisa"
    if any(w in t for w in ["sergio", "alon", "derivado a sergio"]):
        return 1, "Derivados Sergio-Alon"
    if any(w in t for w in ["cierre", "cotizacion", "cotización", "presupuesto formal", "meet", "reunion", "reunión"]):
        return 1, "Derivados Jony"
    return 0, ""


def parse_whatsapp_chat_text(
    content: str,
    default_phone: str = "",
    default_name: str = "",
) -> List[WhatsAppMessage]:
    """
    Parsea exportaciones de chat de WhatsApp estándar en múltiples formatos y formatos AM/PM:
    - [28/01/26, 14:32:10] Juan Perez: Hola, necesito sonda...
    - 28/01/2026, 14:32 - +54 9 351 234-5678: Hola...
    - 28/1/26, 2:30 p.m. - Juan: Mensaje...
    - 28/1/2026 14:30 - Abatech: Hola Juan...
    """
    messages = []
    lines = content.splitlines()

    # Patrones comunes de encabezado de mensaje en WhatsApp:
    pattern1 = re.compile(r"^\[(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[apAP]\.?\s*[mM]\.?)?)\]\s+([^:]+):\s*(.*)$")
    pattern2 = re.compile(r"^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[apAP]\.?\s*[mM]\.?)?)\s+-\s+([^:]+):\s*(.*)$")

    current_msg: Optional[WhatsAppMessage] = None
    company_names = {"abatech", "consultora", "tú", "tu", "you", "me", "nosotros", "ventas", "empresa"}

    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        match1 = pattern1.match(line)
        match2 = pattern2.match(line)
        match = match1 or match2

        if match:
            date_str, time_str, sender, text = match.groups()
            # Omitir mensajes del sistema
            if any(k in text.lower() for k in ["cifrado de extremo a extremo", "cambió el código de seguridad", "creó el grupo", "los mensajes y las llamadas"]):
                continue

            try:
                d_parts = [int(p) for p in re.split(r"[/.-]", date_str.strip())]
                year = d_parts[2] if len(d_parts) > 2 else 2026
                if year < 100:
                    year += 2000
                day, month = d_parts[0], d_parts[1]

                t_clean = time_str.strip().lower().replace(".", "").replace(" ", "")
                is_pm = "pm" in t_clean or "p" in t_clean
                is_am = "am" in t_clean or "a" in t_clean
                t_nums = re.sub(r"[^\d:]", "", t_clean)
                t_parts = [int(p) for p in t_nums.split(":")[:2]]
                hr, mn = t_parts[0], t_parts[1] if len(t_parts) > 1 else 0
                if is_pm and hr < 12:
                    hr += 12
                elif is_am and hr == 12:
                    hr = 0
                dt = datetime.datetime(year, month, day, hr, mn)
            except Exception:
                dt = datetime.datetime.now()

            sender_clean = sender.strip()
            is_company = sender_clean.lower() in company_names or any(c in sender_clean.lower() for c in ["abatech", "consultora"])

            phone = clean_phone_number(sender_clean) if any(c.isdigit() for c in sender_clean) else default_phone
            name = default_name or (sender_clean if not phone else "Cliente WhatsApp")
            if is_company:
                name = "Abatech"

            msg_id = f"wa_{dt.strftime('%Y%m%d%H%M%S')}_{abs(hash(sender + text + str(idx))) % 1000000}"
            current_msg = WhatsAppMessage(
                message_id=msg_id,
                sender_phone=phone,
                sender_name=name,
                timestamp=dt,
                text=text.strip(),
                is_from_me=is_company,
            )
            messages.append(current_msg)
        elif current_msg is not None:
            current_msg.text += " " + line

    return messages


def parse_whatsapp_export_file(
    file_bytes_or_content: bytes | str,
    filename: str = "",
    fallback_phone: str = "",
    fallback_name: str = ""
) -> List[WhatsAppMessage]:
    """
    Parsea archivos de exportación de WhatsApp (.txt o .zip con múltiples .txt).
    Extrae automáticamente el teléfono y nombre del cliente del nombre del archivo si aplica.
    """
    import zipfile
    all_msgs: List[WhatsAppMessage] = []
    
    # Extraer datos de contacto a partir del nombre del archivo si no vienen explícitos
    detected_phone = fallback_phone
    detected_name = fallback_name
    
    clean_stem = Path(filename).stem
    if not detected_phone and any(c.isdigit() for c in clean_stem):
        p_cand = clean_phone_number(clean_stem)
        if len(extract_canonical_phone_digits(p_cand)) >= 8:
            detected_phone = p_cand
            
    if not detected_name:
        clean_name_match = re.search(r"(?:chat de whatsapp con|whatsapp chat with|whatsapp chat -)\s*([^.]+)", clean_stem, re.IGNORECASE)
        if clean_name_match:
            candidate = clean_name_match.group(1).strip()
            if not any(c.isdigit() for c in candidate):
                detected_name = candidate

    # 1. Si es archivo ZIP
    if isinstance(file_bytes_or_content, bytes) and filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(BytesIO(file_bytes_or_content)) as z:
                for entry in z.namelist():
                    if entry.lower().endswith((".txt", ".log")) and not entry.startswith("__MACOSX"):
                        try:
                            raw_txt = z.read(entry).decode("utf-8-sig", errors="ignore")
                            sub_msgs = parse_whatsapp_export_file(raw_txt, filename=entry, fallback_phone=detected_phone, fallback_name=detected_name)
                            all_msgs.extend(sub_msgs)
                        except Exception:
                            pass
        except Exception:
            pass
        return all_msgs

    # 2. Si es archivo de texto TXT
    if isinstance(file_bytes_or_content, bytes):
        try:
            text_content = file_bytes_or_content.decode("utf-8-sig", errors="ignore")
        except Exception:
            text_content = file_bytes_or_content.decode("latin-1", errors="ignore")
    else:
        text_content = str(file_bytes_or_content)

    return parse_whatsapp_chat_text(text_content, default_phone=detected_phone, default_name=detected_name)


# =========================================================================
# RECOLECTOR MULTI-FUENTE (INBOX, API, SIMULACIÓN)
# =========================================================================
def fetch_inbox_messages(inbox_dir: Path = INBOX_DIR, state: WhatsAppSyncState | None = None) -> List[WhatsAppMessage]:
    """Lee todos los archivos de chat nuevos en la carpeta whatsapp_inbox/."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    all_msgs: List[WhatsAppMessage] = []

    for file_path in inbox_dir.glob("*.*"):
        if file_path.suffix.lower() in [".txt", ".log"]:
            try:
                content = file_path.read_text(encoding="utf-8-sig", errors="ignore")
                msgs = parse_whatsapp_chat_text(content)
                for m in msgs:
                    if not m.sender_phone:
                        phone_from_name = clean_phone_number(file_path.stem)
                        if any(c.isdigit() for c in phone_from_name):
                            m.sender_phone = phone_from_name
                    if state is None or not state.is_processed(m.message_id):
                        all_msgs.append(m)
            except Exception:
                pass
        elif file_path.suffix.lower() == ".json":
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else [data]
                for item in items:
                    msg_id = str(item.get("id", item.get("message_id", "")))
                    phone = clean_phone_number(str(item.get("phone", item.get("sender_phone", ""))))
                    name = str(item.get("name", item.get("sender_name", "Cliente WhatsApp")))
                    text = str(item.get("text", item.get("message", "")))
                    is_from_me = bool(item.get("is_from_me", False))
                    dt_str = str(item.get("timestamp", ""))
                    try:
                        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                    except Exception:
                        dt = datetime.datetime.now()
                    
                    if not msg_id:
                        msg_id = f"wa_json_{abs(hash(phone + text + dt_str)) % 1000000}"

                    if state is None or not state.is_processed(msg_id):
                        all_msgs.append(WhatsAppMessage(msg_id, phone, name, dt, text, is_from_me))
            except Exception:
                pass

    return all_msgs


def simulate_incoming_whatsapp_message(
    name: str,
    phone: str,
    text: str,
    timestamp: datetime.datetime | None = None,
    is_from_me: bool = False
) -> WhatsAppMessage:
    """Genera un mensaje de prueba para verificar la sincronización en caliente."""
    dt = timestamp or datetime.datetime.now()
    clean_p = clean_phone_number(phone)
    msg_id = f"sim_{dt.strftime('%Y%m%d%H%M%S')}_{abs(hash(name + clean_p + text + str(is_from_me))) % 1000000}"
    return WhatsAppMessage(
        message_id=msg_id,
        sender_phone=clean_p,
        sender_name=name,
        timestamp=dt,
        text=text,
        is_from_me=is_from_me,
    )


# =========================================================================
# ACTUALIZADOR DE LA BASE DE DATOS EXCEL
# =========================================================================
@_serialized_excel_operation
def register_lead_contact_event(
    excel_path: Path | str,
    lead_id_or_phone: Any,
    message_text: str = "",
    action_type: str = "Seguimiento WhatsApp",
    contact_date: datetime.datetime | None = None
) -> bool:
    """
    Registra instantáneamente un toque o envío de mensaje para un prospecto en Leeds orden.xlsx:
    - Agrega la fecha actual en la columna FECHA CONTACTO disponible.
    - Anota el resumen en CONSULTA.
    - Retorna True si se actualizó exitosamente.
    """
    path = Path(excel_path)
    if not path.exists():
        return False

    dt = contact_date or datetime.datetime.now()
    try:
        with _EXCEL_LOCK:
            wb = pd.read_excel(path, sheet_name=None)
        master = wb.get("Leeds", pd.DataFrame()).copy()
        if master.empty:
            return False

        row_idx = None
        # Buscar por ID_Lead (NUMERO)
        if "NUMERO" in master.columns:
            matches = master[master["NUMERO"].astype(str) == str(lead_id_or_phone)].index
            if not matches.empty:
                row_idx = matches[0]

        # Si no encontró por ID, buscar por teléfono
        if row_idx is None and "PRODUCTO" in master.columns:
            target_clean = clean_phone_number(str(lead_id_or_phone))
            target_digits = re.sub(r"\D", "", target_clean)
            for idx, p in master["PRODUCTO"].dropna().items():
                p_clean = clean_phone_number(str(p))
                p_digits = re.sub(r"\D", "", p_clean)
                if (p_clean and p_clean == target_clean) or (p_digits and p_digits == target_digits):
                    row_idx = idx
                    break

        if row_idx is None:
            return False

        # 1. Asignar fecha en FECHA CONTACTO disponible
        _record_contact_date(master, row_idx, dt)

        # 2. Registrar en CONSULTA
        current_detail = str(master.at[row_idx, "CONSULTA "]) if "CONSULTA " in master.columns and pd.notna(master.at[row_idx, "CONSULTA "]) else ""
        short_msg = message_text.strip()
        if len(short_msg) > 100:
            short_msg = short_msg[:97] + "..."
        entry_txt = f"WA Saliente ({dt.strftime('%d/%m')}): [{action_type}] {short_msg}".strip()
        if entry_txt not in current_detail:
            master.at[row_idx, "CONSULTA "] = f"{current_detail} | {entry_txt}".strip(" |")

        wb["Leeds"] = _compact_contact_dates(master)
        with _EXCEL_LOCK:
            _write_excel_atomic(path, wb)
        return True
    except Exception:
        return False


@_serialized_excel_operation
def update_excel_with_whatsapp_leads(
    excel_path: Path | str,
    messages: List[WhatsAppMessage],
    state: WhatsAppSyncState,
) -> Tuple[int, int]:
    """
    Inserta o actualiza leads en Leeds orden.xlsx a partir de mensajes de WhatsApp:
    - Si es saliente (is_from_me = True): Registra toque de contacto saliente (WA Saliente), fecha y actualiza historial.
    - Si es entrante existente: Agrega toque fechado y actualiza consulta / derivación.
    - Si es nuevo entrante: Asigna ID secuencial, agrega a hoja 'Leeds' y a la hoja de su producto.
    - Retorna: (nuevos_leads, actualizados_leads)
    """
    path = Path(excel_path)
    if not path.exists():
        return 0, 0

    if not messages:
        return 0, 0

    # Crear respaldo de seguridad
    backup_path = path.with_suffix(".xlsx.bak")
    try:
        shutil.copy2(path, backup_path)
    except Exception:
        pass

    with _EXCEL_LOCK:
        wb = pd.read_excel(path, sheet_name=None)
    master = _compact_contact_dates(wb.get("Leeds", pd.DataFrame()).copy())

    if master.empty:
        return 0, 0

    # Determinar el último ID (NUMERO)
    if "NUMERO" in master.columns:
        valid_nums = pd.to_numeric(master["NUMERO"], errors="coerce").dropna()
        max_id = int(valid_nums.max()) if not valid_nums.empty else 0
    else:
        max_id = len(master)

    new_count = 0
    updated_count = 0

    # Índices optimizados para búsqueda de leads
    existing_phones_map: Dict[str, int] = {}
    existing_canonical_map: Dict[str, int] = {}
    existing_suffix8_map: Dict[str, int] = {}
    existing_names_map: Dict[str, int] = {}
    existing_token_map: Dict[int, set[str]] = {}

    if "PRODUCTO" in master.columns:
        for idx, p in master["PRODUCTO"].dropna().items():
            p_str = str(p).strip()
            p_clean = clean_phone_number(p_str)
            p_canon = extract_canonical_phone_digits(p_str)
            if p_clean:
                existing_phones_map[p_clean] = idx
            if p_canon:
                existing_canonical_map[p_canon] = idx
                if len(p_canon) >= 8:
                    existing_suffix8_map[p_canon[-8:]] = idx

    if "NOMBRE" in master.columns:
        for idx, n in master["NOMBRE"].dropna().items():
            n_str = str(n).strip()
            n_norm = normalize_contact_name(n_str)
            if n_norm and len(n_norm) >= 3 and not any(g in n_norm for g in ["lead", "cliente whatsapp", "contacto whatsapp", "cliente"]):
                existing_names_map[n_norm] = idx
                tokens = set(t for t in n_norm.split() if len(t) >= 3)
                if tokens:
                    existing_token_map[idx] = tokens

    for msg in messages:
        if not msg.sender_phone and not msg.sender_name:
            continue

        p_line = detect_product_line(msg.text)
        is_der, der_target = detect_closer_derivation(msg.text)
        phone_raw = str(msg.sender_phone).strip()
        phone_clean = clean_phone_number(phone_raw)
        raw_digits = extract_canonical_phone_digits(phone_raw)
        name_raw = str(msg.sender_name).strip()
        name_norm = normalize_contact_name(name_raw)
        msg_time = msg.timestamp.replace(tzinfo=None) if getattr(msg.timestamp, "tzinfo", None) is not None else msg.timestamp

        # Localizar si ya existe el prospecto
        row_idx = None

        # 1. Búsqueda telefónica directa
        if phone_clean and phone_clean in existing_phones_map:
            row_idx = existing_phones_map[phone_clean]
        elif raw_digits and raw_digits in existing_canonical_map:
            row_idx = existing_canonical_map[raw_digits]
        elif raw_digits and len(raw_digits) >= 8 and raw_digits[-8:] in existing_suffix8_map:
            row_idx = existing_suffix8_map[raw_digits[-8:]]

        # 2. Búsqueda por coincidencia de nombre si el teléfono no arrojó resultado
        if row_idx is None and name_norm and name_norm not in ["cliente whatsapp", "contacto whatsapp", "abatech"]:
            if name_norm in existing_names_map:
                row_idx = existing_names_map[name_norm]
            else:
                msg_tokens = set(t for t in name_norm.split() if len(t) >= 3)
                if msg_tokens:
                    for e_idx, e_tokens in existing_token_map.items():
                        # Si todos los tokens del mensaje están en el lead o viceversa
                        if msg_tokens.issubset(e_tokens) or (len(msg_tokens) >= 2 and e_tokens.issubset(msg_tokens)):
                            row_idx = e_idx
                            break

        if row_idx is not None:
            # Lead ya existente -> Registrar toque
            _record_contact_date(master, row_idx, msg_time)

            # Actualizar detalle de consulta
            current_detail = str(master.at[row_idx, "CONSULTA "]) if "CONSULTA " in master.columns and pd.notna(master.at[row_idx, "CONSULTA "]) else ""
            if msg.is_from_me:
                short_text = msg.text[:120] + ("..." if len(msg.text) > 120 else "")
                entry = f"WA Saliente ({msg_time.strftime('%d/%m')}): {short_text}"
            else:
                prefix = "[RESPUESTA] " if "wa saliente" in current_detail.lower() else ""
                entry = f"WA ({msg_time.strftime('%d/%m')}): {prefix}{msg.text}"

            if entry not in current_detail:
                master.at[row_idx, "CONSULTA "] = f"{current_detail} | {entry}".strip(" |")

            if is_der and "Unnamed: 1" in master.columns:
                master.at[row_idx, "Unnamed: 1"] = 1

            # Si el teléfono del mensaje es válido y el lead no tenía teléfono limpio, actualizarlo
            if phone_clean and "@lid" not in phone_clean and "PRODUCTO" in master.columns:
                curr_p = str(master.at[row_idx, "PRODUCTO"])
                if not curr_p or "@lid" in curr_p or curr_p == "nan":
                    master.at[row_idx, "PRODUCTO"] = phone_clean

            updated_count += 1
        elif not msg.is_from_me:
            # Lead Nuevo Entrante -> Insertar fila maestra
            max_id += 1
            new_row: Dict[str, Any] = {col: pd.NA for col in master.columns}
            new_row["NUMERO"] = max_id
            new_row["NOMBRE"] = name_raw or f"Lead WhatsApp #{max_id}"
            new_row["PRODUCTO"] = phone_clean or phone_raw
            new_row["PRODUCTO.1"] = p_line
            new_row["CONSULTA "] = f"WA ({msg_time.strftime('%d/%m')}): {msg.text}"
            new_row["FECHA CONTACTO"] = msg_time
            new_row["Unnamed: 1"] = 1 if is_der else 0
            new_row["Unnamed: 2"] = 1  # Calificado
            new_row["remarketing 01/06/26"] = 0

            df_new_row = pd.DataFrame([new_row])
            if not df_new_row.empty:
                df_new_row = df_new_row.reindex(columns=master.columns)
                master = _safe_concat([master, df_new_row], ignore_index=True)
            
            new_idx = len(master) - 1
            if phone_clean:
                existing_phones_map[phone_clean] = new_idx
            if raw_digits:
                existing_canonical_map[raw_digits] = new_idx
                if len(raw_digits) >= 8:
                    existing_suffix8_map[raw_digits[-8:]] = new_idx
            if name_norm:
                existing_names_map[name_norm] = new_idx
            new_count += 1

            # Insertar en la hoja correspondiente a su producto si existe
            target_sheet_name = p_line
            if target_sheet_name in wb and not wb[target_sheet_name].empty:
                prod_sheet = wb[target_sheet_name].copy()
                p_row: Dict[str, Any] = {}
                for c in prod_sheet.columns:
                    c_str = str(c).lower()
                    if "nombre" in c_str or "cliente" in c_str: p_row[c] = name_raw
                    elif "telefono" in c_str or ("producto" in c_str and "producto.1" not in c_str): p_row[c] = phone_clean or phone_raw
                    elif "consulta" in c_str: p_row[c] = msg.text
                    elif "fecha" in c_str: p_row[c] = msg.timestamp
                
                df_p_row = pd.DataFrame([{k: v for k, v in p_row.items() if pd.notna(v)}])
                if not df_p_row.empty:
                    for col in prod_sheet.columns:
                        if col not in df_p_row.columns:
                            df_p_row[col] = pd.NA
                    df_p_row = df_p_row[prod_sheet.columns]
                    wb[target_sheet_name] = _safe_concat([prod_sheet, df_p_row], ignore_index=True)

        state.mark_processed(msg.message_id, phone_clean)

    wb["Leeds"] = _compact_contact_dates(master)
    with _EXCEL_LOCK:
        _write_excel_atomic(path, wb)

    return new_count, updated_count


def ensure_whatsapp_bridge_running() -> bool:
    """Verifica si el servidor de puente Baileys está corriendo en el puerto 3001; si no, lo inicia."""
    import os
    import sys
    import shutil
    import subprocess
    import urllib.request
    from urllib.error import HTTPError
    
    try:
        with urllib.request.urlopen("http://127.0.0.1:3001/status", timeout=1) as resp:
            if resp.status == 200:
                return True
    except HTTPError as e:
        if e.code in (200, 401, 403):
            return True
    except Exception:
        pass

    # Detectar ejecutable de Node
    node_bin = shutil.which("node") or shutil.which("node.exe")
    if not node_bin:
        possible_paths = [
            Path(r"C:\Program Files\nodejs\node.exe"),
            Path(r"C:\Program Files (x86)\nodejs\node.exe"),
            Path.home() / "AppData" / "Roaming" / "nvm" / "node.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "node" / "node.exe",
            Path.home() / ".local" / "bin" / "node",
            Path.home() / ".local" / "node" / "bin" / "node",
            Path("/usr/local/bin/node"),
            Path("/usr/bin/node"),
        ]
        for p in possible_paths:
            if p.exists():
                node_bin = str(p)
                break
    if not node_bin:
        node_bin = "node"

    # Configurar PATH en el entorno
    env = os.environ.copy()
    if sys.platform == "win32":
        env["PATH"] = f"C:\\Program Files\\nodejs;{env.get('PATH', '')}"
    else:
        local_bin = str(Path.home() / ".local" / "bin")
        local_node = str(Path.home() / ".local" / "node" / "bin")
        env["PATH"] = f"{local_bin}:{local_node}:{env.get('PATH', '')}"

    # Intentar iniciarlo
    bridge_script = Path("whatsapp_bridge/server.js").resolve()
    if bridge_script.exists():
        try:
            kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "env": env,
                "cwd": str(bridge_script.parent.parent.resolve()),
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["start_new_session"] = True

            subprocess.Popen([node_bin, str(bridge_script)], **kwargs)
            return True
        except Exception:
            return False
    return False


def fetch_api_messages(config_path: Path = CONFIG_FILE, state: WhatsAppSyncState | None = None) -> List[WhatsAppMessage]:
    """Consulta la API de WhatsApp (Bridge local, Meta Cloud API o Evolution API) si está configurada."""
    messages: List[WhatsAppMessage] = []

    # 1. Consultar el puente local Baileys (siempre activo en puerto 3001)
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:3001/messages", timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                for item in data:
                    msg_id = str(item.get("id", ""))
                    if state and state.is_processed(msg_id):
                        continue
                    phone = clean_phone_number(str(item.get("phone", "")))
                    name = str(item.get("name", "Cliente WhatsApp"))
                    text = str(item.get("text", ""))
                    is_from_me = bool(item.get("is_from_me", False))
                    dt_str = str(item.get("timestamp", ""))
                    try:
                        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                    except Exception:
                        dt = datetime.datetime.now()
                    
                    if (phone or name) and text:
                        messages.append(WhatsAppMessage(msg_id, phone, name, dt, text, is_from_me))
    except Exception:
        pass

    if not config_path.exists():
        return messages

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return messages

    provider = cfg.get("provider", "whatsapp_bridge")

    if provider == "evolution_api":
        gw = cfg.get("gateway_settings", {})
        server_url = gw.get("server_url", "http://localhost:8080").rstrip("/")
        instance = gw.get("instance_name", "consultora_crm")
        api_key = gw.get("api_key", "")
        
        try:
            import requests
            headers = {"apikey": api_key} if api_key else {}
            resp = requests.get(f"{server_url}/chat/findMessages/{instance}", headers=headers, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("messages", [])
                for item in items:
                    msg_id = str(item.get("id", item.get("key", {}).get("id", "")))
                    if state and state.is_processed(msg_id):
                        continue
                    
                    remote_jid = item.get("key", {}).get("remoteJid", "")
                    phone = clean_phone_number(remote_jid.split("@")[0])
                    name = item.get("pushName", "Cliente WhatsApp")
                    text = item.get("message", {}).get("conversation", "") or item.get("message", {}).get("extendedTextMessage", {}).get("text", "")
                    ts = item.get("messageTimestamp", None)
                    dt = datetime.datetime.fromtimestamp(int(ts)) if ts else datetime.datetime.now()
                    
                    if phone and text:
                        messages.append(WhatsAppMessage(msg_id, phone, name, dt, text))
        except Exception:
            pass

    return messages


# =========================================================================
# ORQUESTADOR PRINCIPAL
# =========================================================================
@_serialized_excel_operation
def sync_whatsapp_leads(
    excel_path: Path | str = "Leeds orden.xlsx",
    inbox_dir: Path | str = "whatsapp_inbox",
    state_file: Path | str = STATE_FILE,
    config_path: Path | str = CONFIG_FILE,
    extra_messages: List[WhatsAppMessage] | None = None,
) -> WhatsAppSyncResult:
    """
    Ejecuta el ciclo completo de sincronización de WhatsApp:
    1. Carga el estado incremental anterior.
    2. Recolecta mensajes no leídos desde el inbox / API / mensajes encolados.
    3. Extrae datos, intenciones y enriquece leads.
    4. Actualiza Leeds orden.xlsx de forma segura.
    5. Guarda el nuevo estado y timestamp.
    """
    state = WhatsAppSyncState(Path(state_file))
    result = WhatsAppSyncResult()

    inbox_path = Path(inbox_dir)
    inbox_path.mkdir(parents=True, exist_ok=True)

    # 1. Recolectar mensajes de la carpeta inbox
    msgs = fetch_inbox_messages(inbox_path, state)

    # 2. Recolectar mensajes de la API si está configurada
    api_msgs = fetch_api_messages(Path(config_path), state)
    msgs.extend(api_msgs)

    # 3. Agregar mensajes extras o simulados si existen
    if extra_messages:
        for m in extra_messages:
            if not state.is_processed(m.message_id):
                msgs.append(m)

    result.processed_messages = len(msgs)

    if not msgs:
        result.details.append("No se detectaron mensajes nuevos sin procesar.")
        return result

    # 3. Actualizar la base de datos de Leads
    try:
        new_cnt, upd_cnt = update_excel_with_whatsapp_leads(excel_path, msgs, state)
        result.new_leads = new_cnt
        result.updated_leads = upd_cnt
        result.details.append(f"✓ {new_cnt} leads nuevos insertados.")
        result.details.append(f"✓ {upd_cnt} contactos existentes actualizados.")
        state.total_synced_leads += new_cnt
        state.last_sync_iso = datetime.datetime.now().isoformat()
        state.save()
    except Exception as exc:
        result.errors.append(f"Error al actualizar la base de datos: {exc}")

    return result


@_serialized_excel_operation
def import_and_sync_chat_history(
    messages: List[WhatsAppMessage],
    excel_path: Path | str = "Leeds orden.xlsx",
    state: WhatsAppSyncState | None = None,
) -> WhatsAppSyncResult:
    """
    Motor de consolidación e importación masiva de historiales completos de WhatsApp:
    - Agrupa todos los mensajes recibidos y enviados por contacto (teléfono y nombre).
    - Ordena cronológicamente las conversaciones.
    - Asigna y distribuye todas las fechas de interacción en las columnas FECHA CONTACTO correlativas.
    - Extrae el número total de toques (Cant_Contactos), líneas de producto, derivaciones e historial de diálogo.
    - Enriquece leads existentes y crea nuevos leads para cualquier conversación previa no registrada en la BD.
    """
    result = WhatsAppSyncResult()
    path = Path(excel_path)
    if not path.exists() or not messages:
        return result

    result.processed_messages = len(messages)

    # 1. Agrupar mensajes por contacto
    contact_groups: Dict[str, List[WhatsAppMessage]] = {}
    for m in messages:
        c_p = extract_canonical_phone_digits(m.sender_phone)
        c_n = normalize_contact_name(m.sender_name)
        if c_p and len(c_p) >= 8:
            key = f"phone_{c_p}"
        elif c_n and c_n not in ["cliente whatsapp", "contacto whatsapp", "abatech", ""]:
            key = f"name_{c_n}"
        elif m.sender_phone:
            key = f"phone_{m.sender_phone}"
        else:
            continue
        contact_groups.setdefault(key, []).append(m)

    if not contact_groups:
        result.details.append("No se identificaron contactos válidos en los mensajes.")
        return result

    # 2. Cargar Excel
    backup_path = path.with_suffix(".xlsx.bak")
    try:
        shutil.copy2(path, backup_path)
    except Exception:
        pass

    wb = pd.read_excel(path, sheet_name=None)
    master = _compact_contact_dates(wb.get("Leeds", pd.DataFrame()).copy())
    if master.empty:
        result.errors.append("La hoja 'Leeds' está vacía o no existe.")
        return result

    # Determinar el último ID (NUMERO)
    if "NUMERO" in master.columns:
        valid_nums = pd.to_numeric(master["NUMERO"], errors="coerce").dropna()
        max_id = int(valid_nums.max()) if not valid_nums.empty else 0
    else:
        max_id = len(master)

    # Construir índices
    existing_canonical_map: Dict[str, int] = {}
    existing_suffix8_map: Dict[str, int] = {}
    existing_phones_map: Dict[str, int] = {}
    existing_names_map: Dict[str, int] = {}
    existing_token_map: Dict[int, set[str]] = {}

    if "PRODUCTO" in master.columns:
        for idx, p in master["PRODUCTO"].dropna().items():
            p_str = str(p).strip()
            p_clean = clean_phone_number(p_str)
            p_canon = extract_canonical_phone_digits(p_str)
            if p_clean:
                existing_phones_map[p_clean] = idx
            if p_canon:
                existing_canonical_map[p_canon] = idx
                if len(p_canon) >= 8:
                    existing_suffix8_map[p_canon[-8:]] = idx

    if "NOMBRE" in master.columns:
        for idx, n in master["NOMBRE"].dropna().items():
            n_str = str(n).strip()
            n_norm = normalize_contact_name(n_str)
            if n_norm and len(n_norm) >= 3 and not any(g in n_norm for g in ["lead", "cliente whatsapp", "contacto whatsapp", "cliente"]):
                existing_names_map[n_norm] = idx
                tokens = set(t for t in n_norm.split() if len(t) >= 3)
                if tokens:
                    existing_token_map[idx] = tokens

    new_count = 0
    updated_count = 0

    for key, group_msgs in contact_groups.items():
        # Ordenar cronológicamente
        group_msgs.sort(key=lambda x: x.timestamp)
        
        # Extraer atributos consolidados del contacto
        phone_cand = ""
        name_cand = ""
        detected_products = set()
        is_der = 0
        has_outgoing = False
        contact_dates = []
        dialogue_entries = []

        for gm in group_msgs:
            if gm.is_from_me:
                has_outgoing = True
            if not phone_cand and gm.sender_phone and "@lid" not in gm.sender_phone:
                phone_cand = clean_phone_number(gm.sender_phone)
            if not name_cand and gm.sender_name and gm.sender_name not in ["Cliente WhatsApp", "Contacto WhatsApp", "Abatech"]:
                name_cand = gm.sender_name

            prod = detect_product_line(gm.text)
            if prod and prod != "Sin Especificar":
                detected_products.add(prod)

            d_flag, _ = detect_closer_derivation(gm.text)
            if d_flag:
                is_der = 1

            t_val = gm.timestamp.replace(tzinfo=None) if getattr(gm.timestamp, "tzinfo", None) is not None else gm.timestamp
            contact_dates.append(t_val)

            # Entrada de diálogo
            short_txt = gm.text.strip()
            if len(short_txt) > 100:
                short_txt = short_txt[:97] + "..."
            if gm.is_from_me:
                dialogue_entries.append(f"WA Saliente ({t_val.strftime('%d/%m')}): {short_txt}")
            else:
                dialogue_entries.append(f"WA ({t_val.strftime('%d/%m')}): {short_txt}")

        final_product = list(detected_products)[0] if detected_products else "Sentek"
        if not phone_cand and group_msgs[0].sender_phone:
            phone_cand = clean_phone_number(group_msgs[0].sender_phone)
        if not name_cand:
            name_cand = group_msgs[0].sender_name if group_msgs[0].sender_name not in ["Abatech"] else "Cliente WhatsApp"

        canon_digits = extract_canonical_phone_digits(phone_cand)
        name_norm = normalize_contact_name(name_cand)

        # Buscar coincidencia en la base de datos
        row_idx = None
        if phone_cand and phone_cand in existing_phones_map:
            row_idx = existing_phones_map[phone_cand]
        elif canon_digits and canon_digits in existing_canonical_map:
            row_idx = existing_canonical_map[canon_digits]
        elif canon_digits and len(canon_digits) >= 8 and canon_digits[-8:] in existing_suffix8_map:
            row_idx = existing_suffix8_map[canon_digits[-8:]]

        if row_idx is None and name_norm and name_norm not in ["cliente whatsapp", "contacto whatsapp", "abatech"]:
            if name_norm in existing_names_map:
                row_idx = existing_names_map[name_norm]
            else:
                msg_tokens = set(t for t in name_norm.split() if len(t) >= 3)
                if msg_tokens:
                    for e_idx, e_tokens in existing_token_map.items():
                        if msg_tokens.issubset(e_tokens) or (len(msg_tokens) >= 2 and e_tokens.issubset(msg_tokens)):
                            row_idx = e_idx
                            break

        if row_idx is not None:
            # Actualizar Lead Existente
            contact_date_cols = [c for c in master.columns if "FECHA CONTACTO" in str(c)]
            # Rellenar fechas de contacto cronológicamente
            for dt_item in sorted(list(set(contact_dates))):
                already_placed = False
                for col in contact_date_cols:
                    if pd.notna(master.at[row_idx, col]):
                        try:
                            if pd.to_datetime(master.at[row_idx, col]).date() == dt_item.date():
                                already_placed = True
                                break
                        except Exception:
                            pass
                if not already_placed:
                    placed_now = False
                    for col in contact_date_cols:
                        if pd.isna(master.at[row_idx, col]):
                            master.at[row_idx, col] = dt_item
                            placed_now = True
                            break
                    if not placed_now:
                        new_col = f"FECHA CONTACTO.{len(contact_date_cols)}"
                        master[new_col] = pd.NaT
                        master.at[row_idx, new_col] = dt_item
                        contact_date_cols.append(new_col)

            # Actualizar toques
            curr_toques = int(master.at[row_idx, "Cant_Contactos"]) if "Cant_Contactos" in master.columns and pd.notna(master.at[row_idx, "Cant_Contactos"]) else 1
            master.at[row_idx, "Cant_Contactos"] = max(curr_toques, len(set(contact_dates)))

            # Actualizar consulta con historial
            curr_detail = str(master.at[row_idx, "CONSULTA "]) if "CONSULTA " in master.columns and pd.notna(master.at[row_idx, "CONSULTA "]) else ""
            new_entries = [e for e in dialogue_entries if e not in curr_detail]
            if new_entries:
                master.at[row_idx, "CONSULTA "] = f"{curr_detail} | {' | '.join(new_entries)}".strip(" |")

            if is_der and "Unnamed: 1" in master.columns:
                master.at[row_idx, "Unnamed: 1"] = 1

            if "PRODUCTO.1" in master.columns and (pd.isna(master.at[row_idx, "PRODUCTO.1"]) or str(master.at[row_idx, "PRODUCTO.1"]).strip() in ["", "Sin Especificar"]):
                master.at[row_idx, "PRODUCTO.1"] = final_product

            # Si el lead no tenía teléfono limpio y ahora lo tenemos, actualizarlo
            if phone_cand and "@lid" not in phone_cand and "PRODUCTO" in master.columns:
                curr_p = str(master.at[row_idx, "PRODUCTO"])
                if not curr_p or "@lid" in curr_p or curr_p == "nan":
                    master.at[row_idx, "PRODUCTO"] = phone_cand

            updated_count += 1
        else:
            # Crear Nuevo Lead a partir del Historial
            max_id += 1
            new_row: Dict[str, Any] = {col: pd.NA for col in master.columns}
            new_row["NUMERO"] = max_id
            new_row["NOMBRE"] = name_cand or f"Lead WhatsApp #{max_id}"
            new_row["PRODUCTO"] = phone_cand
            new_row["PRODUCTO.1"] = final_product
            new_row["CONSULTA "] = " | ".join(dialogue_entries)
            new_row["Unnamed: 1"] = 1 if is_der else 0
            new_row["Unnamed: 2"] = 1  # Calificado
            new_row["remarketing 01/06/26"] = 0
            new_row["Cant_Contactos"] = len(set(contact_dates))

            # Distribuir fechas
            unique_dates = sorted(list(set(contact_dates)))
            contact_date_cols = [c for c in master.columns if "FECHA CONTACTO" in str(c)]
            for d_i, d_val in enumerate(unique_dates):
                if d_i < len(contact_date_cols):
                    new_row[contact_date_cols[d_i]] = d_val
                else:
                    new_col_name = f"FECHA CONTACTO.{d_i}"
                    master[new_col_name] = pd.NaT
                    new_row[new_col_name] = d_val

            df_new_row = pd.DataFrame([new_row])
            if not df_new_row.empty:
                df_new_row = df_new_row.reindex(columns=master.columns)
                master = _safe_concat([master, df_new_row], ignore_index=True)

            # Insertar en hoja de producto
            if final_product in wb and not wb[final_product].empty:
                prod_sheet = wb[final_product].copy()
                p_row: Dict[str, Any] = {}
                for c in prod_sheet.columns:
                    c_str = str(c).lower()
                    if "nombre" in c_str or "cliente" in c_str: p_row[c] = name_cand
                    elif "telefono" in c_str or ("producto" in c_str and "producto.1" not in c_str): p_row[c] = phone_cand
                    elif "consulta" in c_str: p_row[c] = " | ".join(dialogue_entries)
                    elif "fecha" in c_str and unique_dates: p_row[c] = unique_dates[0]
                df_p_row = pd.DataFrame([{k: v for k, v in p_row.items() if pd.notna(v)}])
                if not df_p_row.empty:
                    for col in prod_sheet.columns:
                        if col not in df_p_row.columns:
                            df_p_row[col] = pd.NA
                    df_p_row = df_p_row[prod_sheet.columns]
                    wb[final_product] = _safe_concat([prod_sheet, df_p_row], ignore_index=True)

            new_count += 1

        if state is not None:
            for gm in group_msgs:
                state.mark_processed(gm.message_id, phone_cand)

    wb["Leeds"] = _compact_contact_dates(master)
    _write_excel_atomic(path, wb)

    if state is not None:
        state.total_synced_leads += new_count
        state.last_sync_iso = datetime.datetime.now().isoformat()
        state.save()

    result.new_leads = new_count
    result.updated_leads = updated_count
    result.details.append(f"✓ {new_count} nuevos leads descubiertos en el historial.")
    result.details.append(f"✓ {updated_count} leads enriquecidos con su historial completo.")
    return result


def get_whatsapp_history_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de mensajes e historiales disponibles en el sistema."""
    live_file = INBOX_DIR / "live_incoming_messages.json"
    messages = []
    if live_file.exists():
        try:
            messages = json.loads(live_file.read_text(encoding="utf-8"))
            if not isinstance(messages, list):
                messages = []
        except Exception:
            pass

    phone_set = set()
    outgoing = 0
    incoming = 0
    for m in messages:
        p = m.get("phone", "")
        if p:
            phone_set.add(p)
        if m.get("is_from_me"):
            outgoing += 1
        else:
            incoming += 1

    return {
        "total_messages": len(messages),
        "unique_contacts": len(phone_set),
        "outgoing_messages": outgoing,
        "incoming_messages": incoming,
    }


# =========================================================================
# GENERADOR Y ESTADO DE QR CODE / VINCULACIÓN

# =========================================================================
def generate_qr_code_image(data_or_url: str) -> BytesIO:
    """Genera una imagen PNG en memoria con el código QR para vincular WhatsApp."""
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(data_or_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return buf


def _make_bridge_request(
    endpoint: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 5,
    as_bytes: bool = False,
) -> Tuple[bool, Any]:
    """Realiza una petición HTTP autenticada al microservicio WhatsApp Bridge."""
    cfg = get_config()
    base_url = cfg.whatsapp_bridge_url.rstrip("/")
    url = f"{base_url}{endpoint}"
    
    headers: Dict[str, str] = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cfg.whatsapp_bridge_token:
        headers["Authorization"] = f"Bearer {cfg.whatsapp_bridge_token}"

    import urllib.request
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status in (200, 201):
                raw = resp.read()
                if as_bytes:
                    return True, raw
                try:
                    return True, json.loads(raw.decode("utf-8"))
                except Exception:
                    return True, raw.decode("utf-8")
            return False, f"HTTP Error {resp.status}"
    except Exception as exc:
        return False, str(exc)


def get_whatsapp_gateway_status(config_path: Path = CONFIG_FILE) -> Dict[str, Any]:
    """
    Determina el estado de conexión del gateway de WhatsApp y retorna el QR Code criptográfico oficial.
    """
    ensure_whatsapp_bridge_running()
    
    # 1. Verificar primero el WhatsApp Bridge Multi-Device local (con autenticación por token)
    ok, b_data = _make_bridge_request("/status", timeout=3)
    if ok and isinstance(b_data, dict):
        if b_data.get("connected"):
            return {
                "connected": True,
                "status": "CONECTADO",
                "provider": "WhatsApp Web Multi-Device (Bridge)",
                "phone": b_data.get("phone", ""),
                "message": f"WhatsApp Business vinculado exitosamente: +{b_data.get('phone', '')}",
                "qr_png": None,
            }
        elif b_data.get("has_qr"):
            # Descargar imagen real del QR con auth
            ok_qr, png_bytes = _make_bridge_request("/qr.png", timeout=3, as_bytes=True)
            if ok_qr and isinstance(png_bytes, (bytes, bytearray)):
                return {
                    "connected": False,
                    "status": "ESPERANDO_QR",
                    "provider": "WhatsApp Web Multi-Device (Bridge)",
                    "message": "Escanee el código QR oficial desde WhatsApp Business en su teléfono.",
                    "qr_png": BytesIO(png_bytes),
                }

    cfg: Dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass

    provider = cfg.get("provider", "whatsapp_bridge")

    if provider == "meta_cloud_api":
        api = cfg.get("api_settings", {})
        token = api.get("access_token", "")
        phone_id = api.get("phone_number_id", "")
        is_configured = bool(token and phone_id)
        return {
            "connected": is_configured,
            "status": "API_CLOUD_CONECTADA" if is_configured else "API_CLOUD_PENDIENTE",
            "provider": "Meta WhatsApp Cloud API",
            "message": "Conectado directamente a los servidores de Meta WhatsApp." if is_configured else "Pendiente de ingresar Access Token y Phone Number ID en whatsapp_config.json.",
            "qr_png": None,
        }

    # Modo Inbox / Fallback
    return {
        "connected": False,
        "status": "INICIANDO_BRIDGE",
        "provider": "WhatsApp Web Multi-Device",
        "message": "Iniciando servicio de WhatsApp Web Bridge protegido...",
        "qr_png": None,
    }


def request_whatsapp_pairing_code(phone: str) -> Dict[str, Any]:
    """Solicita un código de vinculación de 8 dígitos para vincular con el número de teléfono con autenticación."""
    ensure_whatsapp_bridge_running()
    ok, res = _make_bridge_request("/request-pairing-code", method="POST", payload={"phone": phone}, timeout=8)
    if ok and isinstance(res, dict):
        return res
    return {"ok": False, "error": str(res) if res else "No se pudo conectar con el servicio de WhatsApp."}


def reset_whatsapp_session() -> Dict[str, Any]:
    """Restablece la sesión local de WhatsApp y fuerza la regeneración del QR / handshake con autenticación."""
    auth_dir = Path("whatsapp_bridge/auth_info_baileys")
    ensure_whatsapp_bridge_running()
    import time
    
    ok, res = _make_bridge_request("/reset-session", method="POST", payload={}, timeout=4)
    if ok and isinstance(res, dict):
        time.sleep(1.0)
        return res

    if auth_dir.exists():
        try:
            shutil.rmtree(auth_dir, ignore_errors=True)
        except Exception:
            pass

    ensure_whatsapp_bridge_running()
    time.sleep(1.2)
    return {"ok": True, "message": "Sesión reiniciada limpiamente. Generando nuevo código QR..."}



# =========================================================================
# AUTO-SINCRONIZACIÓN CONTINUA EN SEGUNDO PLANO (TIEMPO REAL)
# =========================================================================
_AUTO_SYNC_THREAD: threading.Thread | None = None
_AUTO_SYNC_RUNNING = False


def start_background_auto_sync(excel_path: Path | str = "Leeds orden.xlsx", interval_seconds: int = 3) -> None:
    """
    Inicia un hilo autónomo en segundo plano que escucha y actualiza automáticamente
    los leads de WhatsApp en tiempo real sin requerir que el usuario presione ningún botón.
    """
    global _AUTO_SYNC_THREAD, _AUTO_SYNC_RUNNING
    if _AUTO_SYNC_RUNNING and _AUTO_SYNC_THREAD is not None and _AUTO_SYNC_THREAD.is_alive():
        return

    _AUTO_SYNC_RUNNING = True

    # Start the persistent linked-device bridge even when the QR page is never opened.
    ensure_whatsapp_bridge_running()

    def _sync_worker():
        while _AUTO_SYNC_RUNNING:
            try:
                sync_whatsapp_leads(excel_path=excel_path)
            except Exception:
                pass
            time.sleep(interval_seconds)

    _AUTO_SYNC_THREAD = threading.Thread(target=_sync_worker, daemon=True, name="WhatsAppAutoSyncWorker")
    _AUTO_SYNC_THREAD.start()


def stop_background_auto_sync() -> None:
    """Detiene el hilo de auto-sincronización en segundo plano."""
    global _AUTO_SYNC_RUNNING
    _AUTO_SYNC_RUNNING = False


def is_background_sync_active() -> bool:
    """Indica si el worker de auto-sincronización en tiempo real está activo."""
    return _AUTO_SYNC_RUNNING and _AUTO_SYNC_THREAD is not None and _AUTO_SYNC_THREAD.is_alive()


def get_lead_chat_timeline(lead_row: pd.Series | Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrae y unifica la cronología de mensajes y notas de interacción para un lead:
    - Consulta_Detalle (fragmentos WA entrantes, salientes y notas CRM)
    - live_incoming_messages.json / archivos en whatsapp_inbox/
    Retorna lista de mensajes: [{"sender": str, "text": str, "time": str, "is_lead": bool, "type": str}]
    """
    timeline: List[Dict[str, Any]] = []
    phone = str(lead_row.get("Telefono", "")).strip()
    clean_p = clean_phone_number(phone)
    raw_digits = extract_canonical_phone_digits(phone)
    contact_name = sanitize_display_name(str(lead_row.get("Contacto", "Cliente")).strip())
    contact_norm = normalize_contact_name(contact_name)
    contact_tokens = set(t for t in contact_norm.split() if len(t) >= 3)
    detail = str(lead_row.get("Consulta_Detalle", "")).strip()

    seen_texts = set()

    # 1. Parsear live_incoming_messages.json
    live_file = INBOX_DIR / "live_incoming_messages.json"
    if live_file.exists():
        try:
            items = json.loads(live_file.read_text(encoding="utf-8"))
            for item in items:
                msg_name = str(item.get("name", "")).strip()
                msg_name_norm = normalize_contact_name(msg_name)
                msg_text = str(item.get("text", "")).strip()
                msg_phone = str(item.get("phone", "")).strip()
                clean_msg_p = clean_phone_number(msg_phone)
                msg_digits = extract_canonical_phone_digits(msg_phone)
                is_from_me = bool(item.get("is_from_me", False))
                msg_time = str(item.get("timestamp", ""))[:16].replace("T", " ")
                
                # Match por nombre o teléfono
                phone_match = bool(
                    (clean_p and clean_p in clean_msg_p) or 
                    (raw_digits and msg_digits and (raw_digits == msg_digits or raw_digits[-8:] == msg_digits[-8:]))
                )
                msg_tokens = set(t for t in msg_name_norm.split() if len(t) >= 3)
                name_match = bool(
                    contact_norm and msg_name_norm and (
                        contact_norm in msg_name_norm or 
                        msg_name_norm in contact_norm or
                        (contact_tokens and msg_tokens and contact_tokens.issubset(msg_tokens))
                    )
                )
                
                if (phone_match or name_match) and msg_text not in seen_texts:
                    seen_texts.add(msg_text)
                    timeline.append({
                        "sender": "Abatech" if is_from_me else sanitize_display_name(contact_name or msg_name),
                        "text": msg_text,
                        "time": msg_time,
                        "is_lead": not is_from_me,
                        "type": "whatsapp_out" if is_from_me else "whatsapp_in"
                    })
        except Exception:
            pass

    # 2. Parsear Consulta_Detalle si no vino de live o para notas históricas
    if detail and detail.lower() != "nan":
        parts = re.split(r"[|\n]+", detail)
        for part in parts:
            p = part.strip()
            if not p or p in seen_texts:
                continue
            seen_texts.add(p)

            # Mensajes salientes (WA Saliente)
            wa_saliente_match = re.search(r"WA\s*Saliente\s*\(([^)]+)\):\s*(.*)", p, re.IGNORECASE)
            # Mensajes entrantes (WA)
            wa_entrante_match = re.search(r"WA\s*\(([^)]+)\):\s*(.*)", p, re.IGNORECASE)

            if wa_saliente_match:
                t_str, txt = wa_saliente_match.groups()
                timeline.append({
                    "sender": "Abatech",
                    "text": txt.strip(),
                    "time": t_str.strip(),
                    "is_lead": False,
                    "type": "whatsapp_out"
                })
            elif wa_entrante_match:
                t_str, txt = wa_entrante_match.groups()
                timeline.append({
                    "sender": contact_name,
                    "text": txt.strip(),
                    "time": t_str.strip(),
                    "is_lead": True,
                    "type": "whatsapp_in"
                })
            else:
                timeline.append({
                    "sender": "Registro CRM",
                    "text": p,
                    "time": "Histórico",
                    "is_lead": True,
                    "type": "crm_note"
                })

    if not timeline and detail:
        timeline.append({
            "sender": contact_name,
            "text": detail,
            "time": "Inicial",
            "is_lead": True,
            "type": "crm_note"
        })

    return timeline
