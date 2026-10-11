import pandas as pd
import pytest
from pathlib import Path

from finance_app.lead_intelligence import (
    load_and_enrich_leads,
    extract_meetings_and_technical_leads,
    compute_meeting_kpis,
)


def test_extract_meetings_and_technical_leads_mock():
    df_sample = pd.DataFrame([
        {
            'ID_Lead': 1,
            'Contacto': 'German Lote',
            'Telefono': '3574 63-8297',
            'Linea_Producto': 'Raphael',
            'Consulta_Detalle': 'Mas info-Derivado a Jony | WA (27/08): Si a las 14 hs coordinamos meet | 140 ha maiz y trigo',
            'Provincia': 'Cordoba',
            'Localidad': 'Rio Primero',
            'Lead_Score': 75,
            'Ultimo_Contacto_Label': 'Hoy',
            'Convertido_Derivado': 1
        },
        {
            'ID_Lead': 2,
            'Contacto': 'Willy Gutierrez',
            'Telefono': '2262 61-4835',
            'Linea_Producto': 'Sentek',
            'Consulta_Detalle': '49ha de papas - Necochea (sergio) | Sonda Sentek',
            'Provincia': 'Buenos Aires',
            'Localidad': 'Necochea',
            'Lead_Score': 65,
            'Ultimo_Contacto_Label': 'Hace 5 dias',
            'Convertido_Derivado': 0
        },
        {
            'ID_Lead': 3,
            'Contacto': 'Jose Maria',
            'Telefono': '3464 69-6996',
            'Linea_Producto': 'Sentek',
            'Consulta_Detalle': 'Meet con Celina para evaluar instalacion',
            'Provincia': 'Santa Fe',
            'Localidad': 'Casilda',
            'Lead_Score': 60,
            'Ultimo_Contacto_Label': 'Hace 10 dias',
            'Convertido_Derivado': 0
        },
    ])

    df_res = extract_meetings_and_technical_leads(df_sample)
    assert len(df_res) == 3

    # Validar lead 1
    l1 = df_res[df_res['ID_Lead'] == 1].iloc[0]
    assert l1['Closer'] == 'Jony'
    assert l1['Superficie_Num'] == 140.0
    assert 'Maíz' in l1['Cultivos'] or 'Trigo' in l1['Cultivos']
    assert 'Meet' in l1['Tipo_Evento']

    # Validar lead 2
    l2 = df_res[df_res['ID_Lead'] == 2].iloc[0]
    assert l2['Closer'] == 'Sergio'
    assert l2['Superficie_Num'] == 49.0
    assert 'Papa' in l2['Cultivos']

    # Validar lead 3
    l3 = df_res[df_res['ID_Lead'] == 3].iloc[0]
    assert l3['Closer'] == 'Celina'
    assert 'Meet' in l3['Tipo_Evento']

    # Validar KPIs
    kpis = compute_meeting_kpis(df_res)
    assert kpis.total_reuniones_derivaciones == 3
    assert kpis.superficie_total_ha == 189.0  # 140 + 49
    assert kpis.closers_activos_count >= 2


def test_extract_meetings_real_dataset():
    orig_excel = Path('Leeds orden.xlsx')
    if not orig_excel.exists():
        pytest.skip('No se encuentra Leeds orden.xlsx')

    sheets = load_and_enrich_leads(orig_excel)
    master = sheets['Leeds']
    df_res = extract_meetings_and_technical_leads(master)

    assert not df_res.empty
    assert len(df_res) >= 10
    
    # Debe haber encontrado registros con Jony, Luisa, Sergio, y superficies relevantes
    assert any(df_res['Closer'] == 'Jony')
    assert any(df_res['Closer'] == 'Luisa')
    assert any(df_res['Closer'] == 'Sergio')
    assert df_res['Superficie_Num'].max() >= 100.0

    kpis = compute_meeting_kpis(df_res)
    assert kpis.total_reuniones_derivaciones >= 10
    assert kpis.superficie_total_ha >= 1000.0
