from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import re

from finance_app.lead_intelligence import extract_geo_from_phone, clean_product_line
from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("commercial_analytics")


@dataclass
class CommercialKPISummary:
    total_inversion_ars: float
    total_alcance: int
    total_conversaciones: int
    cpl_promedio_ars: float
    cpm_promedio_ars: float
    total_oportunidades: int
    presupuesto_cotizado_total: float
    closers_activos: int


@dataclass
class CommercialAnalyticsResult:
    kpis: CommercialKPISummary
    df_spend: pd.DataFrame
    df_monthly_summary: pd.DataFrame
    df_product_summary: pd.DataFrame
    df_opportunities: pd.DataFrame
    df_closers_summary: pd.DataFrame
    df_social: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_report_notes: pd.DataFrame = field(default_factory=pd.DataFrame)


def load_and_analyze_commercial_data(file_path: Optional[str | Path | Any] = None) -> Optional[CommercialAnalyticsResult]:
    """
    Carga, limpia y analiza exhaustivamente la base de datos de Pauta Publicitaria y Gastos Comerciales (Comercial.xlsx).
    """
    cfg = get_config()
    if file_path is None or file_path == "Comercial.xlsx":
        source = cfg.resolve_commercial_path()
    elif isinstance(file_path, (str, Path)):
        source = Path(file_path)
    else:
        source = file_path

    if isinstance(source, Path) and not source.exists():
        logger.warning(f"Archivo comercial no encontrado en: {source}")
        return None

    try:
        wb = pd.read_excel(source, sheet_name=None)
        logger.info(f"Cargado dataset comercial desde '{source}' ({len(wb)} hojas)")
    except Exception as e:
        logger.error(f"Error al leer archivo Excel comercial '{source}': {e}", exc_info=True)
        return None
    months = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
              'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    spend_records = []
    opp_records = []

    for m in months:
        if m not in wb:
            continue
        df = wb[m]
        if df.empty:
            continue

        # -------------------------------------------------------------
        # 1. EXTRACCIÓN DE PAUTA PUBLICITARIA Y GASTOS (Filas 0 y 1)
        # -------------------------------------------------------------
        inv_row = df.iloc[0]
        alc_row = df.iloc[1] if len(df) > 1 else pd.Series()

        prod_cols = {}
        for c in df.columns:
            c_str = str(c).strip().lower()
            if c_str.startswith('campaña:'):
                prod_cols[str(c).split(':', 1)[1].strip()] = c
            elif 'sentek' in c_str: prod_cols['Sentek'] = c
            elif 'davis' in c_str: prod_cols['Davis'] = c
            elif 'gsi' in c_str or 'galgon ag' in c_str: prod_cols['GSI'] = c
            elif 'jardin' in c_str or 'galcon gar' in c_str: prod_cols['Jardinería'] = c
            elif 'raphael' in c_str: prod_cols['Raphael'] = c
            elif c_str == 'meta ads sin desglose': prod_cols['Meta Ads sin desglose'] = c
            elif c_str.startswith('meta ads regional'):
                prod_cols[str(c).strip()] = c
            elif 'total' in c_str: prod_cols['Total'] = c

        for p_name, col_name in prod_cols.items():
            if p_name == 'Total':
                continue
            inv_val = inv_row.get(col_name)
            alc_val = str(alc_row.get(col_name, ''))

            # Limpieza de monto
            try:
                inv_clean = float(str(inv_val).replace('$', '').replace(',', '').strip())
                if np.isnan(inv_clean):
                    inv_clean = 0.0
            except Exception:
                inv_clean = 0.0

            # Extracción de alcance y conversaciones
            reach_num = 0
            conv_num = 0
            if pd.notna(alc_val) and alc_val and alc_val.lower() != 'nan':
                match_conv = re.search(r'\((\d+)\s*conversacion', alc_val, re.IGNORECASE)
                if match_conv:
                    conv_num = int(match_conv.group(1))
                reach_match = re.search(r'^([0-9\.\,]+)', alc_val.strip())
                if reach_match:
                    r_str = reach_match.group(1).replace('.', '').replace(',', '')
                    if r_str.isdigit():
                        reach_num = int(r_str)

            if inv_clean > 0 or conv_num > 0 or reach_num > 0:
                cpl = (inv_clean / conv_num) if conv_num > 0 else 0.0
                cpm = ((inv_clean / reach_num) * 1000) if reach_num > 0 else 0.0
                spend_records.append({
                    'Mes': m,
                    'Producto': p_name,
                    'Inversion_ARS': inv_clean,
                    'Alcance': reach_num,
                    'Conversaciones': conv_num,
                    'CPL_ARS': round(cpl, 2),
                    'CPM_ARS': round(cpm, 2)
                })

        # -------------------------------------------------------------
        # 2. EXTRACCIÓN DE OPORTUNIDADES Y COTIZACIONES (Fila 7+)
        # -------------------------------------------------------------
        client_row_idx = None
        for idx, row in df.iterrows():
            if row.astype(str).str.contains('Cliente', case=False).any():
                client_row_idx = idx
                break

        if client_row_idx is not None:
            sub_df = df.iloc[client_row_idx + 1:].copy()
            for _, r in sub_df.iterrows():
                cliente = str(r.iloc[0]).strip()
                if cliente in ['nan', '', 'None', 'NaT'] or pd.isna(r.iloc[0]):
                    continue

                contacto = str(r.iloc[1]).strip() if len(r) > 1 else ''
                producto = str(r.iloc[2]).strip() if len(r) > 2 else ''
                monto = r.iloc[3] if len(r) > 3 else 0.0
                prob_cierre = r.iloc[4] if len(r) > 4 else ''
                derivado = str(r.iloc[5]).strip() if len(r) > 5 else ''
                comentarios = str(r.iloc[6]).strip() if len(r) > 6 else ''

                # Limpieza de monto cotizado
                try:
                    monto_num = float(str(monto).replace('$', '').replace(',', '').replace('USD', '').replace('usd', '').strip())
                    if np.isnan(monto_num):
                        monto_num = 0.0
                except Exception:
                    monto_num = 0.0

                # Geografía desde el contacto telefónico
                prov, loc, reg = extract_geo_from_phone(contacto) if contacto and contacto != 'nan' else ('Otras Provincias', 'Sin Localidad', 'Otras Regiones')

                opp_records.append({
                    'Mes': m,
                    'Cliente': cliente,
                    'Contacto': contacto if contacto != 'nan' else '',
                    'Producto': clean_product_line(producto) if producto != 'nan' else 'Sin Especificar',
                    'Monto_Cotizado': monto_num,
                    'Prob_Cierre': prob_cierre if pd.notna(prob_cierre) and str(prob_cierre) != 'nan' else 'En curso',
                    'Derivado_A': derivado if derivado != 'nan' else 'Sin Asignar',
                    'Comentarios_Tecnicos': comentarios if comentarios != 'nan' else '',
                    'Provincia': prov,
                    'Localidad': loc,
                    'Region': reg
                })

    df_spend = pd.DataFrame(spend_records)
    df_opps = pd.DataFrame(opp_records)

    if not df_opps.empty:
        for str_col in ["Cliente", "Contacto", "Producto", "Prob_Cierre", "Derivado_A", "Comentarios_Tecnicos", "Provincia", "Localidad", "Region"]:
            if str_col in df_opps.columns:
                df_opps[str_col] = df_opps[str_col].fillna("").astype(str)
    # 3. TABLAS RESUMEN Y AGREGACIONES
    # -------------------------------------------------------------
    if not df_spend.empty:
        # Resumen mensual
        month_order = {m: i for i, m in enumerate(months)}
        df_monthly = (
            df_spend.groupby('Mes', as_index=False)
            .agg(
                Inversion_Total=('Inversion_ARS', 'sum'),
                Alcance_Total=('Alcance', 'sum'),
                Conversaciones_Total=('Conversaciones', 'sum'),
            )
        )
        df_monthly['CPL_Promedio'] = np.where(
            df_monthly['Conversaciones_Total'] > 0,
            (df_monthly['Inversion_Total'] / df_monthly['Conversaciones_Total']).round(2),
            0.0
        )
        df_monthly['CPM_Promedio'] = np.where(
            df_monthly['Alcance_Total'] > 0,
            ((df_monthly['Inversion_Total'] / df_monthly['Alcance_Total']) * 1000).round(2),
            0.0
        )
        df_monthly['sort_key'] = df_monthly['Mes'].map(month_order)
        df_monthly = df_monthly.sort_values(by='sort_key').drop(columns=['sort_key']).reset_index(drop=True)

        # Resumen por producto
        df_product = (
            df_spend.groupby('Producto', as_index=False)
            .agg(
                Inversion_Total=('Inversion_ARS', 'sum'),
                Alcance_Total=('Alcance', 'sum'),
                Conversaciones_Total=('Conversaciones', 'sum'),
            )
        )
        tot_inv = df_product['Inversion_Total'].sum()
        df_product['Pct_Inversion'] = ((df_product['Inversion_Total'] / tot_inv) * 100).round(1) if tot_inv > 0 else 0.0
        df_product['CPL_Promedio'] = np.where(
            df_product['Conversaciones_Total'] > 0,
            (df_product['Inversion_Total'] / df_product['Conversaciones_Total']).round(2),
            0.0
        )
        df_product = df_product.sort_values(by='Inversion_Total', ascending=False).reset_index(drop=True)
    else:
        df_monthly = pd.DataFrame()
        df_product = pd.DataFrame()

    # Resumen de Closers / Comerciales
    if not df_opps.empty:
        # Extraer nombre limpio del closer
        def clean_closer(d: str) -> str:
            d_str = str(d).strip()
            if 'jony' in d_str.lower(): return 'Jony'
            elif 'luisa' in d_str.lower(): return 'Luisa'
            elif 'agustina' in d_str.lower(): return 'Agustina'
            elif 'sergio' in d_str.lower() or 'alon' in d_str.lower(): return 'Sergio / Alon'
            elif d_str in ['', 'nan', 'Sin Asignar']: return 'Sin Asignar'
            return d_str

        df_opps['Closer_Limpio'] = df_opps['Derivado_A'].apply(clean_closer)
        df_closers = (
            df_opps.groupby('Closer_Limpio', as_index=False)
            .agg(
                Oportunidades=('Cliente', 'count'),
                Monto_Total_Cotizado=('Monto_Cotizado', 'sum')
            )
            .sort_values(by='Oportunidades', ascending=False)
            .reset_index(drop=True)
        )
    else:
        df_closers = pd.DataFrame()

    # Totales Globales
    tot_inv_g = float(df_spend['Inversion_ARS'].sum()) if not df_spend.empty else 0.0
    tot_alc_g = int(df_spend['Alcance'].sum()) if not df_spend.empty else 0
    tot_conv_g = int(df_spend['Conversaciones'].sum()) if not df_spend.empty else 0
    cpl_g = (tot_inv_g / tot_conv_g) if tot_conv_g > 0 else 0.0
    cpm_g = ((tot_inv_g / tot_alc_g) * 1000) if tot_alc_g > 0 else 0.0
    tot_opps_g = len(df_opps)
    tot_cotizado_g = float(df_opps['Monto_Cotizado'].sum()) if not df_opps.empty else 0.0
    closers_count = df_closers['Closer_Limpio'].nunique() if not df_closers.empty else 0

    kpis = CommercialKPISummary(
        total_inversion_ars=tot_inv_g,
        total_alcance=tot_alc_g,
        total_conversaciones=tot_conv_g,
        cpl_promedio_ars=cpl_g,
        cpm_promedio_ars=cpm_g,
        total_oportunidades=tot_opps_g,
        presupuesto_cotizado_total=tot_cotizado_g,
        closers_activos=closers_count,
    )

    return CommercialAnalyticsResult(
        kpis=kpis,
        df_spend=df_spend,
        df_monthly_summary=df_monthly,
        df_product_summary=df_product,
        df_opportunities=df_opps,
        df_closers_summary=df_closers,
        df_social=wb.get('Redes sociales', pd.DataFrame()),
        df_report_notes=wb.get('Observaciones reportes', pd.DataFrame()),
    )
