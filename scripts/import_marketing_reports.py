"""Incorpora los cuatro reportes revisados de mayo-agosto de 2026 al Excel comercial.

Conserva los originales en un ZIP y su texto en el libro. No elimina las fuentes.
Los importes contradictorios o aproximados quedan como observaciones.
"""
from pathlib import Path
from datetime import datetime
import os
import shutil
import zipfile

import openpyxl
from openpyxl.styles import Font, Alignment

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'markdown'
    names = ['Reporte Mayo.docx.md', 'Reporte Junio 2026.docx.md',
             'Reporte Julio.docx.md', 'Reporte Agosto.docx.md']
    texts = {name: (source / name).read_text(encoding='utf-8') for name in names}
    target = ROOT / 'Comercial.xlsx'
    backup = ROOT / 'backups' / ('reportes_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True)
    shutil.copy2(target, backup / target.name)
    with zipfile.ZipFile(backup / 'reportes_originales.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(source / name, arcname=name)
    wb = openpyxl.load_workbook(target)

    def sheet(name, rows):
        if name in wb:
            del wb[name]
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = 24
        return ws

    sheet('Redes sociales', [
        ['Año', 'Mes', 'Visualizaciones', 'Alcance Instagram', 'Visualizaciones anuncios %',
         'Visualizaciones no seguidores %', 'Interacciones', 'Interacciones anuncios %',
         'Interacciones no seguidores %', 'Seguidores cierre', 'Seguidores netos',
         'Visualizaciones publicaciones %', 'Visualizaciones reels %', 'Visualizaciones historias %'],
        [2026, 'Mayo', 31476, None, None, None, 214, 32.7, None, 1282, 46, 71.3, 18.5, 10.2],
        [2026, 'Junio', 19654, 8318, 82.4, 82.2, None, None, None, None, None, None, None, None],
        [2026, 'Julio', 53968, 34523, 95.7, 88.5, 129, 65.1, 83.2, 1346, 46, 82.1, 4.3, 13.6],
        [2026, 'Agosto', 31962, None, 88.4, 89.8, 117, 27.4, 67.9, 1364, None, None, 33.6, None],
    ])
    notes = [
        ['Mes', 'Observación'],
        ['General', 'Ejercicio 2026 según los títulos explícitos de junio y julio. Imágenes de los Markdown son marcadores sin datos recuperables. Texto completo preservado en Fuentes reportes.'],
        ['Mayo', 'Fuente contradictoria: 79 y 77 conversaciones; inversiones 216968,76 y 220938,31. Se conserva la pauta existente sin adjudicar conversaciones ni alcance. El desglose existente suma 216971,11 y el total declarado es 216968,76 (diferencia 2,35).'],
        ['Junio', 'El bloque de interacciones dice Mayo y repite sus cifras; no se asigna a junio. La sección publicitaria corresponde explícitamente a julio. Reels: 69,1% de interacciones; alcance: -36,2%.'],
        ['Julio', 'Inversiones aproximadas en el archivo de junio: Norte 107450, Centro 111364, Sur 72043 (suma aproximada 290857). No se incorporan como importes exactos al total financiero. Falta el gasto exacto y conversaciones; presupuesto previsto 200000.'],
        ['Julio', 'Se conserva cierre explícito de 1346 seguidores. El crecimiento informado de 46 y 3,3% no permite reconstruir con certeza el cierre de junio. Altas 54, bajas 8.'],
        ['Agosto', 'Pauta exacta: 135329,58 y 50 conversaciones; sin desglose por producto/región ni alcance publicitario informado. Presupuesto 200000. No confundir visualizaciones de Instagram con alcance de anuncios.'],
        ['Agosto', 'La referencia a julio dice aproximadamente 1345 seguidores, frente a 1346 del reporte de julio. Se conserva cada cierre directo, sin inferir crecimiento neto. La publicación de 46 mil visualizaciones no se suma al total mensual de 31962.'],
    ]
    sheet('Observaciones reportes', notes)
    rows = [['Archivo', 'Bloque', 'Contenido original']]
    for name, content in texts.items():
        for index, paragraph in enumerate(content.split('\n\n'), 1):
            if paragraph.strip():
                rows.append([name, index, paragraph])
    sheet('Fuentes reportes', rows)
    if 'Agosto' not in wb:
        ws = wb.create_sheet('Agosto')
        ws.append(['AGOSTO', 'Meta Ads sin desglose'])
        ws.append(['Inversion en publicidad', 135329.58])
        ws.append(['Alcance', '(50 conversaciones)'])
        ws.append(['Observación', 'Alcance no informado; campañas Norte, Centro y Sur sin desglose.'])
    else:
        raise RuntimeError('Agosto ya existe: revisar antes de repetir la importación.')
    for month in ('Abril', 'Mayo', 'Julio'):
        wb[month]['A1'] = month.upper()
    temporary = target.with_name('Comercial.import.tmp.xlsx')
    try:
        wb.save(temporary)
        check = openpyxl.load_workbook(temporary, read_only=True)
        assert check['Redes sociales'].max_row == 5
        assert check['Agosto']['B2'].value == 135329.58
        check.close()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Importación completa. Respaldo: {backup}')


if __name__ == '__main__':
    main()
