# Funcionalidades / Features

## Español

- **Datos:** cargar CSV (detección de separador y codificaciones) o XLSX (selección
  de hoja). Normaliza nombres de columnas y muestra hasta 100 filas.
- **Métricas:** filas, columnas, completitud, duplicados y cantidad de variables numéricas.
- **Gráficas:** elegir X, Y opcional y tipo bar/pie/line/scatter. Barras numéricas
  y líneas usan las agregaciones predeterminadas de seaborn; no representan
  automáticamente sumas contables. Las tortas muestran frecuencias.
- **Contabilidad:** elegir categoría e importe. Ingresos: Ventas, Servicios,
  Otros Ingresos. Costos: Costo de Ventas. Gastos: Gastos Operativos, Impuestos,
  Otros Gastos. Coincidencias exactas; categorías desconocidas no se suman al resultado.
  Utilidad bruta = ingresos − costos; utilidad neta = utilidad bruta − gastos.
  Usar importes numéricos positivos y categorías completas.
- **Exportación:** XLSX con resumen y detalle; destino elegido por el usuario.
- **Terminal:** help, stats, preview, clear. No es una shell ni un intérprete Python.
- **API Python:** quality_issues detecta faltantes, duplicados, columnas constantes
  y espacios; numeric_summary calcula cantidad, media, mediana, primera moda,
  extremos, Q1/Q3 y desvío muestral. recommend_chart sugiere una visualización.
  Estas funciones no tienen un panel dedicado en la interfaz actual.

Limitaciones: no limpieza automática, autenticación, balance, flujo de caja,
proyecciones, normas contables ni integración con servicios. Las fechas de CSV
no se convierten automáticamente; convertirlas explícitamente para recomendaciones
temporales desde la API. El estado de resultados es una demostración simplificada.

## English

The GUI imports CSV/XLSX, selects Excel sheets, previews 100 rows, shows quality
metrics, draws bar/pie/line/scatter charts, builds a category-based income statement
and exports summary/detail sheets. Bar and line plots use seaborn's default
aggregation; pie charts display counts.

Accounting uses exact Spanish category names listed above, positive numeric amounts,
and subtracts costs and expenses. Unknown categories do not contribute to totals.
The embedded terminal supports only help/stats/preview/clear.
Python APIs provide quality issues, descriptive statistics and chart recommendations;
they have no dedicated GUI panel. CSV dates require explicit conversion.
No automated cleaning, authentication, balance sheet, cash flow or forecasting is implemented.
