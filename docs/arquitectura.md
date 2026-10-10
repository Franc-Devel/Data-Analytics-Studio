# Arquitectura / Architecture

## Español

Aplicación local por módulos. No hay backend web, base de datos ni API externa.

- `run_app.py`: punto de entrada, instancia FinanceApp y abre el bucle gráfico.
- `finance_app/gui.py`: presentación, selección de archivos, variables y exportación.
- `data_service.py`: validación de archivos, CSV/XLSX, normalización de columnas;
  devuelve LoadedDataset con DataFrame, ruta local y hoja.
- `analysis.py`: funciones de perfil, calidad, estadística y recomendaciones.
- `charts.py`: gráficos Matplotlib/seaborn embebidos en Tk mediante FigureCanvasTkAgg.
- `consulting.py`: catálogo y estado de resultados simplificado.
- `reports.py`: exportación XLSX con openpyxl.
- `examples/`: generador determinista y demo de consola sin credenciales.
- `tests/`: pruebas unitarias del motor de análisis y de importación.

Flujo: selección local → DataFrame en memoria → métricas/gráficas o agregación
contable → exportación opcional. La interfaz coordina; los cálculos se mantienen
fuera de ella. No se persisten automáticamente archivos importados.
Las dependencias están acotadas parcialmente en requirements.txt; no es un lockfile.

## English

Local modular desktop application, with no web backend, database or external API.
The launcher opens FinanceApp. The GUI coordinates local file selection and display;
data_service validates/loads files into pandas DataFrames; analysis computes profiles
and statistics; charts embeds Matplotlib/seaborn in Tk; consulting performs simplified
accounting aggregation; reports writes Excel. Examples and tests run without the GUI.
Input stays in memory until an optional user-requested export. Requirements are not
a fully locked dependency environment.
