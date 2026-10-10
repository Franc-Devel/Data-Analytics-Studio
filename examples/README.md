# Ejemplo reproducible / Reproducible example

Desde la raíz / From the repository root:

```bash
python -m examples.generate_data
python -m examples.demo
```

Genera 21 movimientos ficticios: siete categorías en tres meses. No deriva de datos
reales ni contiene personas, cuentas o contactos. El campo origen marca SINTETICO.
La demo verifica ingresos 75000, costos 24000, gastos 13800 y utilidad neta 37200.
Importes positivos en unidades monetarias ficticias; no representan pesos ni dólares.
La columna origen constante produce una advertencia de calidad intencional.
Para graficar importá el CSV en la interfaz, por ejemplo X=categoria, Y=monto, tipo=bar.
Para contabilidad usá categoria/monto. El reporte Excel se guarda solo si lo solicitás.

Generates 21 fictional records: seven categories across three months, using invented
monetary units. No real source records, people, accounts or contacts are used.
The demo checks income 75000, costs 24000, expenses 13800 and net income 37200.
The constant synthetic marker intentionally triggers a quality warning.
GUI: import the CSV, choose categoria/monto for accounting, and export only if desired.
