import pandas as pd
from typing import Dict, List, Any

# Simple default Chart of Accounts
DEFAULT_CATALOG = {
    "Ingresos": ["Ventas", "Servicios", "Otros Ingresos"],
    "Egresos": ["Costo de Ventas", "Gastos Operativos", "Impuestos", "Otros Gastos"],
    "Activos": ["Caja", "Bancos", "Cuentas por Cobrar", "Inventario", "Activos Fijos"],
    "Pasivos": ["Cuentas por Pagar", "Impuestos por Pagar", "Préstamos"],
    "Patrimonio": ["Capital Social", "Resultados Acumulados"]
}

def generate_income_statement(df: pd.DataFrame, category_column: str, amount_column: str) -> Dict[str, Any]:
    """
    Generates a basic Income Statement (Estado de Resultados) from a DataFrame.
    Assumes df has a column with category names mapping to the catalog, and an amount column.
    """
    if category_column not in df.columns or amount_column not in df.columns:
        return {"error": f"Faltan columnas requeridas ('{category_column}' o '{amount_column}') para el estado de resultados."}
    
    # Simple grouping
    summary = df.groupby(category_column)[amount_column].sum().to_dict()
    
    ingresos_totales = sum(summary.get(cat, 0) for cat in DEFAULT_CATALOG["Ingresos"])
    costos_totales = sum(summary.get(cat, 0) for cat in DEFAULT_CATALOG["Egresos"] if "Costo" in cat)
    gastos_totales = sum(summary.get(cat, 0) for cat in DEFAULT_CATALOG["Egresos"] if "Gasto" in cat or "Impuesto" in cat or "Otros" in cat)
    
    utilidad_bruta = ingresos_totales - costos_totales
    utilidad_neta = utilidad_bruta - gastos_totales
    
    return {
        "Ingresos Totales": ingresos_totales,
        "Costos": costos_totales,
        "Utilidad Bruta": utilidad_bruta,
        "Gastos": gastos_totales,
        "Utilidad Neta": utilidad_neta,
        "Detalle": summary
    }

def get_catalog() -> Dict[str, List[str]]:
    """Returns the Chart of Accounts."""
    return DEFAULT_CATALOG

