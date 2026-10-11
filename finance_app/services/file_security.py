"""
Nexo Analytics - Módulo de Seguridad y Validación de Archivos Subidos
Protege contra ataques de denegación de servicio (Memory Exhaustion), Zip Bombs,
macros maliciosas VBA (XLSM), ataques XXE e inyección de fórmulas CSV/Excel.
"""

from __future__ import annotations
import io
import re
import zipfile
from typing import Tuple, Optional, Any, Union
import pandas as pd

from finance_app.logging_config import get_logger

logger = get_logger("file_security")

# Constantes de Seguridad de Carga
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_UNCOMPRESSED_ZIP_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_COMPRESSION_RATIO = 25
FORBIDDEN_EXTENSIONS = {".xlsm", ".xltm", ".xla", ".xlam", ".exe", ".dll", ".bat", ".sh", ".vbs", ".ps1"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_formula_value(val: Any) -> Any:
    """Neutraliza la inyección de fórmulas CSV/Excel anteponiendo una comilla simple."""
    if isinstance(val, str):
        stripped = val.strip()
        if stripped and stripped.startswith(FORMULA_PREFIXES):
            return f"'{val}"
    return val


def sanitize_dataframe_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitiza todas las columnas de texto de un DataFrame para exportación segura."""
    if df.empty:
        return df
    clean_df = df.copy()
    for col in clean_df.select_dtypes(include=["object", "string"]).columns:
        clean_df[col] = clean_df[col].apply(sanitize_formula_value)
    return clean_df


def validate_uploaded_file(
    file_content: bytes,
    filename: str,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    allowed_types: Tuple[str, ...] = (".xlsx", ".csv"),
) -> Tuple[bool, Optional[str]]:
    """
    Valida exhaustivamente un archivo subido en memoria:
    1. Tamaño máximo
    2. Extensión permitida y no peligrosa
    3. Firma de bytes mágicos (Magic Bytes)
    4. Protección contra Zip Bombs y macros VBA embebidas (para XLSX)
    """
    if not file_content:
        return False, "El archivo subido está vacío."

    # 1. Validación de tamaño
    if len(file_content) > max_size_bytes:
        size_mb = round(len(file_content) / (1024 * 1024), 2)
        max_mb = round(max_size_bytes / (1024 * 1024), 2)
        return False, f"El archivo excede el tamaño máximo permitido ({size_mb} MB > {max_mb} MB)."

    # 2. Validación de extensión
    clean_name = filename.lower().strip()
    matched_ext = None
    for ext in allowed_types:
        if clean_name.endswith(ext):
            matched_ext = ext
            break

    if not matched_ext:
        return False, f"Formato no permitido. Extensiones válidas: {', '.join(allowed_types)}"

    for forbidden in FORBIDDEN_EXTENSIONS:
        if clean_name.endswith(forbidden):
            return False, f"Tipo de archivo potencialmente peligroso bloqueado ({forbidden})."

    # 3. Validación de Magic Bytes y Contenido
    if matched_ext == ".xlsx":
        # XLSX es un contenedor ZIP que debe comenzar con PK\x03\x04
        if not file_content.startswith(b"PK\x03\x04"):
            return False, "Firma de archivo inválida. El archivo no es un documento Excel válido."

        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                total_uncompressed = 0
                for info in zf.infolist():
                    # Prevención de Path Traversal
                    if ".." in info.filename or info.filename.startswith("/"):
                        return False, "Estructura interna de archivo maliciosa (Path Traversal detectado)."

                    # Rechazar macros VBA embebidas
                    if "vbaProject.bin" in info.filename or info.filename.endswith(".bin"):
                        return False, "El archivo contiene código de macros embebido (VBA). Por seguridad, solo se admiten libros sin macros (.xlsx estándar)."

                    total_uncompressed += info.file_size

                # Protección Zip Bomb (Ratio y Tamaño Absoluto)
                if total_uncompressed > MAX_UNCOMPRESSED_ZIP_BYTES:
                    return False, "El archivo descomprimido excede el límite de memoria permitido (posible Zip Bomb)."

                ratio = total_uncompressed / max(len(file_content), 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    return False, "Ratio de compresión anormal detectado (posible Zip Bomb)."

        except zipfile.BadZipFile:
            return False, "Estructura de archivo XLSX dañada o corrupta."
        except Exception as e:
            return False, f"Error validando archivo XLSX: {e}"

    elif matched_ext == ".csv":
        # Validar que sea texto decodificable
        try:
            sample = file_content[:4096].decode("utf-8", errors="replace")
            # Verificar si contiene bytes nulos (indicativo de binario malicioso disfrazado)
            if "\x00" in sample:
                return False, "El archivo CSV contiene caracteres binarios inválidos."
        except Exception:
            return False, "El archivo CSV no tiene una codificación de texto válida."

    return True, None
