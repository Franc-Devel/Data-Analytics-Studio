import pandas as pd
from typing import Dict, Any
from finance_app.logging_config import get_logger

logger = get_logger("reports")

def export_income_statement_to_excel(result: Dict[str, Any], filepath: str) -> bool:
    """
    Exporta el diccionario resultante del Estado de Resultados a un archivo Excel.
    """
    if "error" in result:
        return False
        
    try:
        # Extraemos el detalle
        detalle = result.get("Detalle", {})
        
        # Creamos un dataframe con el resumen
        resumen_data = {
            "Concepto": ["Ingresos Totales", "Costos", "Utilidad Bruta", "Gastos Operativos", "UTILIDAD NETA"],
            "Monto ($)": [
                result.get('Ingresos Totales', 0),
                result.get('Costos', 0),
                result.get('Utilidad Bruta', 0),
                result.get('Gastos', 0),
                result.get('Utilidad Neta', 0)
            ]
        }
        df_resumen = pd.DataFrame(resumen_data)
        
        # Creamos un dataframe con el detalle
        df_detalle = pd.DataFrame(list(detalle.items()), columns=["Categoría", "Monto ($)"])
        
        # Escribimos a Excel
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df_resumen.to_excel(writer, sheet_name="Estado de Resultados", index=False)
            df_detalle.to_excel(writer, sheet_name="Detalle por Categoría", index=False)
            
        logger.info(f"Estado de resultados exportado exitosamente a: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error exportando Estado de Resultados a Excel '{filepath}': {e}", exc_info=True)
        return False
