# Data Analytics Studio

Aplicación de escritorio para explorar CSV/Excel, visualizar datos y preparar un
estado de resultados simplificado. Edición de portfolio de Francisco Delgado.
**Todos los ejemplos incluidos son sintéticos.**

## Español

**Stack:** Python 3.11+, pandas, Tkinter/CustomTkinter, Matplotlib, seaborn y openpyxl.

**Funciones:** importación CSV/XLSX con elección de hoja, vista previa y métricas de
calidad; barras, tortas, líneas y dispersión; estado de resultados por categorías
y exportación a Excel; terminal interna con comandos de consulta.
El motor incluye estadística descriptiva y recomendaciones de gráficos, disponibles
como API Python. La interfaz está en español.

### Instalación y uso

```bash
git clone https://github.com/Franc-Devel/Data-Analytics-Studio.git
cd Data-Analytics-Studio
python -m venv .venv
```

Activar: Linux/macOS `source .venv/bin/activate`; Windows PowerShell
`.venv\Scripts\Activate.ps1`.

```bash
python -m pip install -r requirements.txt
python -m examples.generate_data
python -m examples.demo
python run_app.py
python -m unittest discover -s tests -v
```

Requiere Tk y una sesión gráfica para la interfaz. En Linux puede ser necesario el
paquete Tk de tu distribución; en Windows habilitá **tcl/tk and IDLE** al instalar Python.
La demo de consola y las pruebas no requieren una pantalla.

En la interfaz, importar `examples/data/movimientos_sinteticos.csv`. Para el estado
de resultados elegir `categoria` y `monto`. Usar importes positivos para ingresos
y egresos: el motor resta los egresos. Es un ejemplo educativo simplificado.

**Seguridad y privacidad:** procesamiento local sin credenciales ni servicio remoto.
Los reportes pueden contener datos del archivo importado; usar datos sintéticos
en demos y no agregarlos a Git si contienen información privada.
No incluye cifrado ni anonimización.

Documentación: [funcionalidades](docs/funcionalidades.md),
[arquitectura](docs/arquitectura.md), [revisión de seguridad](docs/seguridad.md)
y [créditos/contexto](docs/creditos.md).
Derivado de un prototipo existente en contexto de aprendizaje. No se afirma autoría
individual exclusiva ni se redistribuye material del curso. No se añade una licencia
abierta sin evidencia de los derechos correspondientes.

## English

Desktop application for CSV/Excel exploration, visualization and a simplified
income statement. Portfolio edition prepared for Francisco Delgado.
**All bundled examples are synthetic.**

**Stack:** Python 3.11+, pandas, Tkinter/CustomTkinter, Matplotlib, seaborn, openpyxl.
Features include sheet selection, data preview, quality metrics, bar/pie/line/scatter
charts, category-based income statements and Excel export. Descriptive statistics
and chart recommendations are also available through the Python API. The UI is Spanish.

Use the installation commands above, activate the virtual environment for your
platform, install requirements and run the generator, console demo or desktop app.
The GUI needs Tk and a graphical session; console examples and tests are headless.
Import `examples/data/movimientos_sinteticos.csv`, then select `categoria` and
`monto` for the income statement. Income and expenses use positive amounts;
expenses are subtracted by the engine.

Processing stays local and needs no credentials. Exports contain imported data;
use synthetic input for demonstrations. There is no encryption or anonymization.
The linked documentation contains English sections. This derives from an existing
learning prototype; exclusive individual authorship is not claimed, course material
is excluded, and no open-source license is added without rights evidence.
