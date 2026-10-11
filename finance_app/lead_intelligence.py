from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import datetime
import pandas as pd
import numpy as np
import re

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("lead_intelligence")


@dataclass
class LeadKPISummary:
    total_leads: int
    convertidos: int
    tasa_conversion_pct: float
    remarketing_total: int
    pct_remarketing: float
    promedio_contactos: float
    leads_hot: int
    leads_warm: int
    leads_cold: int
    dias_promedio_pipeline: float
    recontacto_sugerido: int = 0
    recontacto_urgente: int = 0
    descartados: int = 0
    contactados_hoy: int = 0
    en_seguimiento: int = 0
    total_frios_reactivables: int = 0
    leads_reactivados: int = 0
    tasa_reactivacion_pct: float = 0.0
    lote_diario_count: int = 0



def sanitize_display_name(name: Any) -> str:
    """Elimina emojis y caracteres decorativos para una presentación limpia y profesional."""
    if not name or pd.isna(name):
        return ""
    cleaned = re.sub(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]",
        "",
        str(name)
    )
    return " ".join(cleaned.split())


# Diccionario exhaustivo de Códigos de Área de Argentina
# Estructura: 'codigo': (Provincia_Oficial, Localidad_o_Departamento, Region_Geografica)
AREA_CODES_ARGENTINA = {
    # CABA / AMBA / Buenos Aires
    '11': ('Buenos Aires', 'CABA / Gran Buenos Aires', 'AMBA'),
    '220': ('Buenos Aires', 'Merlo / BsAs Oeste', 'AMBA'),
    '221': ('Buenos Aires', 'La Plata', 'Pampeana'),
    '2221': ('Buenos Aires', 'Magdalena', 'Pampeana'),
    '2223': ('Buenos Aires', 'Brandsen', 'Pampeana'),
    '2224': ('Buenos Aires', 'Glew / San Vicente', 'AMBA'),
    '2225': ('Buenos Aires', 'Gdor. Udaondo', 'Pampeana'),
    '2226': ('Buenos Aires', 'Cañuelas', 'Pampeana'),
    '2227': ('Buenos Aires', 'Lobos', 'Pampeana'),
    '223': ('Buenos Aires', 'Mar del Plata', 'Pampeana'),
    '2241': ('Buenos Aires', 'Chascomús', 'Pampeana'),
    '2242': ('Buenos Aires', 'Lezama', 'Pampeana'),
    '2243': ('Buenos Aires', 'General Belgrano', 'Pampeana'),
    '2244': ('Buenos Aires', 'Las Flores', 'Pampeana'),
    '2245': ('Buenos Aires', 'Dolores', 'Pampeana'),
    '2246': ('Buenos Aires', 'Santa Teresita / Costa', 'Pampeana'),
    '2252': ('Buenos Aires', 'San Clemente del Tuyú', 'Pampeana'),
    '2254': ('Buenos Aires', 'Pinamar', 'Pampeana'),
    '2255': ('Buenos Aires', 'Villa Gesell', 'Pampeana'),
    '2257': ('Buenos Aires', 'Mar de Ajó', 'Pampeana'),
    '2261': ('Buenos Aires', 'Lobería', 'Pampeana'),
    '2262': ('Buenos Aires', 'Necochea / Quequén', 'Pampeana'),
    '2264': ('Buenos Aires', 'Miramar', 'Pampeana'),
    '2265': ('Buenos Aires', 'Coronel Vidal', 'Pampeana'),
    '2266': ('Buenos Aires', 'Balcarce', 'Pampeana'),
    '2267': ('Buenos Aires', 'General Madariaga', 'Pampeana'),
    '2268': ('Buenos Aires', 'Ayacucho', 'Pampeana'),
    '2271': ('Buenos Aires', 'San Miguel del Monte', 'Pampeana'),
    '2272': ('Buenos Aires', 'Navarro', 'Pampeana'),
    '2273': ('Buenos Aires', 'Carmen de Areco', 'Pampeana'),
    '2274': ('Buenos Aires', 'Roque Pérez', 'Pampeana'),
    '2281': ('Buenos Aires', 'Azul', 'Pampeana'),
    '2283': ('Buenos Aires', 'Tapalqué', 'Pampeana'),
    '2284': ('Buenos Aires', 'Olavarría', 'Pampeana'),
    '2285': ('Buenos Aires', 'Laprida', 'Pampeana'),
    '2286': ('Buenos Aires', 'General La Madrid', 'Pampeana'),
    '2291': ('Buenos Aires', 'General Alvarado', 'Pampeana'),
    '2292': ('Buenos Aires', 'Rauch', 'Pampeana'),
    '2296': ('Buenos Aires', 'Ayacucho', 'Pampeana'),
    '2297': ('Buenos Aires', 'Benito Juárez', 'Pampeana'),
    '230': ('Buenos Aires', 'Pilar', 'AMBA'),
    '2302': ('La Pampa', 'General Pico', 'Pampeana'),
    '2314': ('Buenos Aires', 'Bolívar', 'Pampeana'),
    '2316': ('Buenos Aires', 'Daireaux', 'Pampeana'),
    '2317': ('Buenos Aires', '9 de Julio', 'Pampeana'),
    '2320': ('Buenos Aires', 'José C. Paz / Malvinas', 'AMBA'),
    '2323': ('Buenos Aires', 'Luján', 'Pampeana'),
    '2324': ('Buenos Aires', 'Mercedes', 'Pampeana'),
    '2325': ('Buenos Aires', 'San Andrés de Giles', 'Pampeana'),
    '2326': ('Buenos Aires', 'San Antonio de Areco', 'Pampeana'),
    '2342': ('Buenos Aires', 'Bragado', 'Pampeana'),
    '2343': ('Buenos Aires', 'Norberto de la Riestra', 'Pampeana'),
    '2344': ('Buenos Aires', 'Saladillo', 'Pampeana'),
    '2345': ('Buenos Aires', '25 de Mayo', 'Pampeana'),
    '2346': ('Buenos Aires', 'Chivilcoy', 'Pampeana'),
    '2352': ('Buenos Aires', 'Chacabuco', 'Pampeana'),
    '2353': ('Buenos Aires', 'General Arenales', 'Pampeana'),
    '2354': ('Buenos Aires', 'Vedia', 'Pampeana'),
    '2355': ('Buenos Aires', 'Lincoln', 'Pampeana'),
    '2356': ('Buenos Aires', 'General Pinto', 'Pampeana'),
    '2357': ('Buenos Aires', 'Carlos Tejedor', 'Pampeana'),
    '2358': ('Buenos Aires', 'Los Toldos', 'Pampeana'),
    '236': ('Buenos Aires', 'Junín', 'Pampeana'),
    '237': ('Buenos Aires', 'Moreno / GBA', 'AMBA'),
    '2392': ('Buenos Aires', 'Trenque Lauquen', 'Pampeana'),
    '2393': ('Buenos Aires', 'Pellegrini', 'Pampeana'),
    '2394': ('Buenos Aires', 'Salliqueló', 'Pampeana'),
    '2395': ('Buenos Aires', 'Carlos Casares', 'Pampeana'),
    '2396': ('Buenos Aires', 'Pehuajó', 'Pampeana'),
    '2473': ('Buenos Aires', 'Colón', 'Pampeana'),
    '2474': ('Buenos Aires', 'Rojas', 'Pampeana'),
    '2475': ('Buenos Aires', 'Salto', 'Pampeana'),
    '2477': ('Buenos Aires', 'Pergamino', 'Pampeana'),
    '2478': ('Buenos Aires', 'Arrecifes', 'Pampeana'),
    '249': ('Buenos Aires', 'Tandil', 'Pampeana'),
    '291': ('Buenos Aires', 'Bahía Blanca', 'Pampeana'),
    '2920': ('Río Negro', 'Viedma', 'Patagonia'),
    '2921': ('Buenos Aires', 'Coronel Dorrego', 'Pampeana'),
    '2922': ('Buenos Aires', 'Coronel Pringles', 'Pampeana'),
    '2923': ('Buenos Aires', 'Pigüé', 'Pampeana'),
    '2924': ('Buenos Aires', 'Darregueira', 'Pampeana'),
    '2925': ('Buenos Aires', 'Médanos', 'Pampeana'),
    '2926': ('Buenos Aires', 'Coronel Suárez', 'Pampeana'),
    '2927': ('Buenos Aires', 'Monte Hermoso', 'Pampeana'),
    '2928': ('Buenos Aires', 'Punta Alta', 'Pampeana'),
    '2929': ('Buenos Aires', 'Carmen de Patagones', 'Pampeana'),
    '2931': ('Río Negro', 'Río Colorado', 'Patagonia'),
    '2932': ('Buenos Aires', 'Punta Alta', 'Pampeana'),
    '2933': ('Buenos Aires', 'Carhué', 'Pampeana'),
    '2934': ('Río Negro', 'San Antonio Oeste', 'Patagonia'),
    '2935': ('Buenos Aires', 'Rivera', 'Pampeana'),
    '2936': ('Buenos Aires', 'Tornquist', 'Pampeana'),
    '2982': ('Buenos Aires', 'Adolfo Gonzales Chaves', 'Pampeana'),
    '2983': ('Buenos Aires', 'Tres Arroyos', 'Pampeana'),
    '3327': ('Buenos Aires', 'Benavídez / Tigre', 'AMBA'),
    '3329': ('Buenos Aires', 'San Pedro', 'Pampeana'),
    '336': ('Buenos Aires', 'San Nicolás de los Arroyos', 'Pampeana'),
    '3382': ('Buenos Aires', 'Rufino / BsAs', 'Pampeana'),
    '3385': ('Córdoba', 'Laboulaye', 'Centro'),
    '3387': ('Córdoba', 'General Levalle', 'Centro'),
    '3388': ('Buenos Aires', 'General Villegas', 'Pampeana'),
    '348': ('Buenos Aires', 'Escobar / Maschwitz', 'AMBA'),
    '3487': ('Buenos Aires', 'Zárate', 'Pampeana'),
    '3489': ('Buenos Aires', 'Campana', 'Pampeana'),

    # Mendoza
    '260': ('Mendoza', 'San Rafael / General Alvear', 'Cuyo'),
    '2604': ('Mendoza', 'San Rafael', 'Cuyo'),
    '261': ('Mendoza', 'Gran Mendoza / Capital / Maipú', 'Cuyo'),
    '2622': ('Mendoza', 'Valle de Uco / Tunuyán / Tupungato', 'Cuyo'),
    '2624': ('Mendoza', 'Uspallata', 'Cuyo'),
    '2625': ('Mendoza', 'General Alvear', 'Cuyo'),
    '2626': ('Mendoza', 'La Paz', 'Cuyo'),
    '263': ('Mendoza', 'San Martín / Rivadavia', 'Cuyo'),
    '2634': ('Mendoza', 'San Martín / Rivadavia / Junín', 'Cuyo'),

    # San Juan
    '264': ('San Juan', 'San Juan Capital / Caucete', 'Cuyo'),
    '2644': ('San Juan', 'San Juan Capital', 'Cuyo'),
    '2645': ('San Juan', 'San Juan Sur / Pocito', 'Cuyo'),
    '2646': ('San Juan', 'Valle Fértil', 'Cuyo'),
    '2647': ('San Juan', 'Jáchal', 'Cuyo'),
    '2648': ('San Juan', 'Calingasta / Barreal', 'Cuyo'),

    # San Luis
    '2652': ('San Luis', 'San Luis Capital', 'Cuyo'),
    '2655': ('San Luis', 'Concarán', 'Cuyo'),
    '2656': ('San Luis', 'Merlo', 'Cuyo'),
    '2657': ('San Luis', 'Villa Mercedes', 'Cuyo'),
    '266': ('San Luis', 'San Luis Capital', 'Cuyo'),

    # Córdoba
    '351': ('Córdoba', 'Córdoba Capital', 'Centro'),
    '3521': ('Córdoba', 'Deán Funes', 'Centro'),
    '3522': ('Córdoba', 'Villa de María', 'Centro'),
    '3524': ('Córdoba', 'Villa del Totoral', 'Centro'),
    '3525': ('Córdoba', 'Jesús María / Colonia Caroya', 'Centro'),
    '353': ('Córdoba', 'Villa María', 'Centro'),
    '3532': ('Córdoba', 'Oliva', 'Centro'),
    '3533': ('Córdoba', 'Las Varillas', 'Centro'),
    '3534': ('Córdoba', 'Villa María / Villa Nueva', 'Centro'),
    '3537': ('Córdoba', 'Bell Ville', 'Centro'),
    '3541': ('Córdoba', 'Villa Carlos Paz', 'Centro'),
    '3542': ('Córdoba', 'Salsacate', 'Centro'),
    '3543': ('Córdoba', 'Sierras Chicas / Villa Allende', 'Centro'),
    '3544': ('Córdoba', 'Villa Dolores / Traslasierra', 'Centro'),
    '3546': ('Córdoba', 'Santa Rosa de Calamuchita', 'Centro'),
    '3547': ('Córdoba', 'Alta Gracia', 'Centro'),
    '3548': ('Córdoba', 'La Falda / Cosquín', 'Centro'),
    '3549': ('Córdoba', 'Cruz del Eje', 'Centro'),
    '3562': ('Córdoba', 'Morteros / Brinkmann', 'Centro'),
    '3563': ('Córdoba', 'Balnearia', 'Centro'),
    '3564': ('Córdoba', 'San Francisco', 'Centro'),
    '3571': ('Córdoba', 'Río Tercero', 'Centro'),
    '3572': ('Córdoba', 'Oncativo / Río Segundo', 'Centro'),
    '3573': ('Córdoba', 'Villa del Rosario', 'Centro'),
    '3574': ('Córdoba', 'Río Primero / Monte Cristo', 'Centro'),
    '3575': ('Córdoba', 'Santa Rosa de Río Primero', 'Centro'),
    '3576': ('Córdoba', 'Arroyito', 'Centro'),
    '358': ('Córdoba', 'Río Cuarto', 'Centro'),
    '3582': ('Córdoba', 'Sampacho', 'Centro'),
    '3583': ('Córdoba', 'Vicuña Mackenna', 'Centro'),
    '3584': ('Córdoba', 'La Carlota', 'Centro'),
    '3585': ('Córdoba', 'Adelia María / Bengolea', 'Centro'),
    '3586': ('Córdoba', 'Río Cuarto Sur', 'Centro'),

    # Santa Fe
    '3401': ('Santa Fe', 'El Trébol / San Jorge', 'Centro'),
    '3402': ('Santa Fe', 'Arroyo Seco', 'Centro'),
    '3404': ('Santa Fe', 'Gálvez / San Carlos', 'Centro'),
    '3405': ('Santa Fe', 'Helvecia', 'Centro'),
    '3406': ('Santa Fe', 'San Carlos Centro', 'Centro'),
    '3407': ('Santa Fe', 'Ramallo / Villa Constitución', 'Centro'),
    '3408': ('Santa Fe', 'San Cristóbal', 'Centro'),
    '3409': ('Santa Fe', 'Moises Ville', 'Centro'),
    '341': ('Santa Fe', 'Rosario', 'Centro'),
    '342': ('Santa Fe', 'Santa Fe Capital / Santo Tomé', 'Centro'),
    '3424': ('Santa Fe', 'Santa Fe Capital', 'Centro'),
    '3425': ('Santa Fe', 'Santa Fe Capital', 'Centro'),
    '3426': ('Santa Fe', 'Santa Fe Capital', 'Centro'),
    '3460': ('Santa Fe', 'Santa Teresa', 'Centro'),
    '3462': ('Santa Fe', 'Venado Tuerto', 'Centro'),
    '3463': ('Santa Fe', 'Canals / Venado Tuerto', 'Centro'),
    '3464': ('Santa Fe', 'Casilda', 'Centro'),
    '3465': ('Santa Fe', 'Firmat', 'Centro'),
    '3466': ('Santa Fe', 'Barrancas', 'Centro'),
    '3467': ('Santa Fe', 'Cruz Alta / Los Surgentes', 'Centro'),
    '3468': ('Santa Fe', 'Corral de Bustos', 'Centro'),
    '3469': ('Santa Fe', 'Acebal', 'Centro'),
    '3471': ('Santa Fe', 'Cañada de Gómez', 'Centro'),
    '3472': ('Córdoba', 'Marcos Juárez', 'Centro'),
    '3476': ('Santa Fe', 'San Lorenzo', 'Centro'),
    '3482': ('Santa Fe', 'Reconquista / Avellaneda', 'Centro'),
    '3483': ('Santa Fe', 'Vera', 'Centro'),
    '3491': ('Santa Fe', 'Ceres', 'Centro'),
    '3492': ('Santa Fe', 'Rafaela', 'Centro'),
    '3493': ('Santa Fe', 'Sunchales', 'Centro'),
    '3496': ('Santa Fe', 'Esperanza', 'Centro'),
    '3497': ('Santa Fe', 'Llambi Campbell', 'Centro'),
    '3498': ('Santa Fe', 'San Justo', 'Centro'),

    # Entre Ríos
    '343': ('Entre Ríos', 'Paraná', 'Litoral'),
    '3435': ('Entre Ríos', 'Nogoyá', 'Litoral'),
    '3436': ('Entre Ríos', 'Victoria', 'Litoral'),
    '3437': ('Entre Ríos', 'La Paz', 'Litoral'),
    '3438': ('Entre Ríos', 'Bovril', 'Litoral'),
    '3442': ('Entre Ríos', 'Concepción del Uruguay', 'Litoral'),
    '3444': ('Entre Ríos', 'Gualeguay', 'Litoral'),
    '3445': ('Entre Ríos', 'Rosario del Tala', 'Litoral'),
    '3446': ('Entre Ríos', 'Gualeguaychú', 'Litoral'),
    '3447': ('Entre Ríos', 'Colón', 'Litoral'),
    '345': ('Entre Ríos', 'Concordia', 'Litoral'),
    '3454': ('Entre Ríos', 'Federal', 'Litoral'),
    '3455': ('Entre Ríos', 'Villaguay', 'Litoral'),
    '3456': ('Entre Ríos', 'Chajarí', 'Litoral'),
    '3458': ('Entre Ríos', 'San José de Feliciano', 'Litoral'),

    # Tucumán
    '381': ('Tucumán', 'San Miguel de Tucumán', 'NOA'),
    '3814': ('Tucumán', 'San Miguel de Tucumán', 'NOA'),
    '3815': ('Tucumán', 'San Miguel de Tucumán', 'NOA'),
    '3816': ('Tucumán', 'San Miguel de Tucumán', 'NOA'),
    '3863': ('Tucumán', 'Monteros', 'NOA'),
    '3865': ('Tucumán', 'Concepción', 'NOA'),
    '3867': ('Tucumán', 'Aguilares', 'NOA'),
    '3869': ('Tucumán', 'Simoca', 'NOA'),

    # Salta
    '387': ('Salta', 'Salta Capital', 'NOA'),
    '3873': ('Salta', 'Tartagal', 'NOA'),
    '3876': ('Salta', 'Metán', 'NOA'),
    '3877': ('Salta', 'Joaquín V. González', 'NOA'),
    '3878': ('Salta', 'Orán', 'NOA'),
    '3868': ('Salta', 'Cafayate', 'NOA'),

    # Jujuy
    '388': ('Jujuy', 'San Salvador de Jujuy', 'NOA'),
    '3884': ('Jujuy', 'San Pedro de Jujuy', 'NOA'),
    '3885': ('Jujuy', 'Ledesma', 'NOA'),
    '3886': ('Jujuy', 'Libertador Gral. San Martín', 'NOA'),
    '3887': ('Jujuy', 'Tilcara / Humahuaca', 'NOA'),
    '3888': ('Jujuy', 'La Quiaca', 'NOA'),

    # Santiago del Estero
    '3841': ('Santiago del Estero', 'Monte Quemado', 'NOA'),
    '3843': ('Santiago del Estero', 'Quimilí / Añatuya', 'NOA'),
    '3844': ('Santiago del Estero', 'Añatuya', 'NOA'),
    '3845': ('Santiago del Estero', 'Loreto', 'NOA'),
    '3846': ('Santiago del Estero', 'Bandera', 'NOA'),
    '385': ('Santiago del Estero', 'Santiago del Estero Capital', 'NOA'),
    '3854': ('Santiago del Estero', 'Frías', 'NOA'),
    '3855': ('Santiago del Estero', 'Santiago del Estero', 'NOA'),
    '3856': ('Santiago del Estero', 'Termas de Río Hondo', 'NOA'),
    '3857': ('Santiago del Estero', 'Fernández', 'NOA'),
    '3858': ('Santiago del Estero', 'Termas de Río Hondo', 'NOA'),

    # Chaco
    '362': ('Chaco', 'Resistencia', 'NEA'),
    '364': ('Chaco', 'Presidencia Roque Sáenz Peña', 'NEA'),
    '3725': ('Chaco', 'General San Martín', 'NEA'),
    '3731': ('Chaco', 'Charata', 'NEA'),
    '3732': ('Chaco', 'Castelli', 'NEA'),
    '3734': ('Chaco', 'Machagai', 'NEA'),
    '3735': ('Chaco', 'Villa Ángela', 'NEA'),

    # Corrientes
    '3772': ('Corrientes', 'Paso de los Libres', 'NEA'),
    '3773': ('Corrientes', 'Mercedes', 'NEA'),
    '3774': ('Corrientes', 'Curuzú Cuatiá', 'NEA'),
    '3775': ('Corrientes', 'Monte Caseros', 'NEA'),
    '3777': ('Corrientes', 'Goya', 'NEA'),
    '3781': ('Corrientes', 'Bella Vista', 'NEA'),
    '3782': ('Corrientes', 'Saladas', 'NEA'),
    '3783': ('Corrientes', 'Corrientes Capital', 'NEA'),
    '3786': ('Corrientes', 'Ituzaingó', 'NEA'),
    '379': ('Corrientes', 'Corrientes Capital', 'NEA'),
    '3794': ('Corrientes', 'Corrientes Capital', 'NEA'),

    # Misiones
    '3751': ('Misiones', 'Eldorado', 'NEA'),
    '3754': ('Misiones', 'Leandro N. Alem', 'NEA'),
    '3755': ('Misiones', 'Oberá', 'NEA'),
    '3756': ('Misiones', 'Santo Tomé', 'NEA'),
    '3757': ('Misiones', 'Puerto Iguazú', 'NEA'),
    '3758': ('Misiones', 'Apóstoles', 'NEA'),
    '376': ('Misiones', 'Posadas', 'NEA'),

    # Formosa
    '370': ('Formosa', 'Formosa Capital', 'NEA'),
    '3711': ('Formosa', 'Clorinda', 'NEA'),
    '3715': ('Formosa', 'Las Lomitas', 'NEA'),
    '3716': ('Formosa', 'Ingeniero Juárez', 'NEA'),
    '3718': ('Formosa', 'Clorinda', 'NEA'),

    # La Rioja
    '380': ('La Rioja', 'La Rioja Capital', 'NOA'),
    '3821': ('La Rioja', 'Arauco', 'NOA'),
    '3825': ('La Rioja', 'Chilecito', 'NOA'),
    '3826': ('La Rioja', 'Chepes', 'NOA'),
    '3827': ('La Rioja', 'Villa Unión', 'NOA'),

    # Catamarca
    '383': ('Catamarca', 'San Fernando del Valle de Catamarca', 'NOA'),
    '3832': ('Catamarca', 'Recreo', 'NOA'),
    '3833': ('Catamarca', 'Catamarca Capital', 'NOA'),
    '3835': ('Catamarca', 'Andalgalá / Belén / Tinogasta', 'NOA'),
    '3837': ('Catamarca', 'Tinogasta', 'NOA'),
    '3838': ('Catamarca', 'Santa María', 'NOA'),

    # La Pampa
    '2302': ('La Pampa', 'General Pico', 'Pampeana'),
    '2331': ('La Pampa', 'Realicó', 'Pampeana'),
    '2333': ('La Pampa', 'Eduardo Castex', 'Pampeana'),
    '2334': ('La Pampa', 'General Acha', 'Pampeana'),
    '2335': ('La Pampa', 'Intendente Alvear', 'Pampeana'),
    '2952': ('La Pampa', 'General Acha', 'Pampeana'),
    '2953': ('La Pampa', 'Victorica', 'Pampeana'),
    '2954': ('La Pampa', 'Santa Rosa', 'Pampeana'),

    # Río Negro
    '2920': ('Río Negro', 'Viedma', 'Patagonia'),
    '2931': ('Río Negro', 'Río Colorado', 'Patagonia'),
    '2934': ('Río Negro', 'San Antonio Oeste', 'Patagonia'),
    '294': ('Río Negro', 'San Carlos de Bariloche', 'Patagonia'),
    '298': ('Río Negro', 'General Roca / Alto Valle', 'Patagonia'),
    '2984': ('Río Negro', 'General Roca', 'Patagonia'),

    # Neuquén
    '2942': ('Neuquén', 'Zapala', 'Patagonia'),
    '2948': ('Neuquén', 'Chos Malal', 'Patagonia'),
    '2972': ('Neuquén', 'San Martín de los Andes', 'Patagonia'),
    '299': ('Neuquén', 'Neuquén Capital', 'Patagonia'),

    # Chubut
    '280': ('Chubut', 'Trelew / Puerto Madryn', 'Patagonia'),
    '2945': ('Chubut', 'Esquel', 'Patagonia'),
    '2963': ('Chubut', 'Gobernador Costa', 'Patagonia'),
    '297': ('Chubut', 'Comodoro Rivadavia', 'Patagonia'),
    '2974': ('Chubut', 'Comodoro Rivadavia', 'Patagonia'),

    # Santa Cruz
    '2962': ('Santa Cruz', 'Puerto San Julián', 'Patagonia'),
    '2966': ('Santa Cruz', 'Río Gallegos', 'Patagonia'),

    # Tierra del Fuego
    '2901': ('Tierra del Fuego', 'Ushuaia', 'Patagonia'),
    '2964': ('Tierra del Fuego', 'Río Grande', 'Patagonia'),
}


def extract_geo_from_phone(phone: Any) -> Tuple[str, str, str]:
    """
    Extrae (Provincia, Localidad, Region) de Argentina a partir del código de área del teléfono.
    """
    clean = re.sub(r'[^\d]', '', str(phone))
    if clean.startswith('549'):
        clean = clean[3:]
    elif clean.startswith('54'):
        clean = clean[2:]
        
    for code in sorted(AREA_CODES_ARGENTINA.keys(), key=lambda x: -len(x)):
        if clean.startswith(code):
            return AREA_CODES_ARGENTINA[code]
            
    return ('Otras Provincias', 'Sin Localidad', 'Otras Regiones')


def clean_product_line(p: Any) -> str:
    """Normaliza los nombres de línea de producto."""
    if pd.isna(p):
        return 'Sin Especificar'
    p_str = str(p).strip()
    p_low = p_str.lower()
    if 'davis' in p_low:
        return 'Davis'
    if 'sentek' in p_low:
        return 'Sentek'
    if 'jardin' in p_low:
        return 'Jardinería'
    if 'raphael' in p_low or 'rafael' in p_low:
        return 'Raphael'
    if 'automat' in p_low:
        return 'Automatismo'
    if 'abatech' in p_low:
        return 'Abatech'
    if 'gsi' in p_low:
        return 'GSI PRO'
    if p_str in ['-', '']:
        return 'Sin Especificar'
    if re.match(r'^\d', p_str):
        return 'Sin Especificar'
    return p_str


def extract_intent_tags(text: Any) -> List[str]:
    """Clasifica los intereses y temas mediante procesamiento de texto (NLP ligero)."""
    if pd.isna(text):
        return ["General"]
    t = str(text).lower()
    tags = []
    
    if any(k in t for k in ["estacion", "estación", "davis", "vantage", "clima", "metereol", "meteorol"]):
        tags.append("Estación Meteorológica")
    if any(k in t for k in ["sonda", "humedad", "sentek", "drill", "suelo"]):
        tags.append("Sonda de Humedad")
    if any(k in t for k in ["valvula", "válvula", "alivio", "bermad", "hidraul", "hidrául"]):
        tags.append("Válvulas & Hidráulica")
    if any(k in t for k in ["caudal", "caudalimetro", "caudalímetro"]):
        tags.append("Caudalímetros")
    if any(k in t for k in ["jardin", "jardín", "organico", "orgánico", "parque", "riego"]):
        tags.append("Riego & Jardinería")
    if any(k in t for k in ["presupuest", "precio", "cotiz", "costo", "promo"]):
        tags.append("Presupuesto / Precios")
    if any(k in t for k in ["catalogo", "catálogo", "info"]):
        tags.append("Catálogo / Información")
    if any(k in t for k in ["derivado", "jony", "luisa", "sergio", "alon", "meet", "reunion", "reunión"]):
        tags.append("Derivado / En Cierre")
    if any(k in t for k in ["capacitac", "capacitación", "curso"]):
        tags.append("Capacitaciones")
    if any(k in t for k in ["no desea", "no le interesa", "descart"]):
        tags.append("Descartado")
        
    return tags if tags else ["Consulta General"]


def calculate_lead_score(row: pd.Series) -> Tuple[int, str]:
    """
    Algoritmo de Data Science / Lead Scoring (0 a 100 puntos):
    Puntúa el nivel de compromiso y probabilidad de cierre.
    """
    score = 30  # Base score
    
    is_conv = bool(row.get("Convertido_Derivado") == 1 or str(row.get("Convertido_Derivado")).lower() == "true")
    if is_conv:
        score += 45
        
    cant_cont = int(row.get("Cant_Contactos", 1))
    score += min(25, cant_cont * 5)
    
    tags = row.get("Intent_Tags", [])
    if any(t in tags for t in ["Sonda de Humedad", "Estación Meteorológica", "Derivado / En Cierre", "Válvulas & Hidráulica"]):
        score += 15
    if "Descartado" in tags:
        score = max(5, score - 50)
        
    prod = str(row.get("Linea_Producto", ""))
    if prod in ["Sentek", "Davis"]:
        score += 5

    is_reactivado = bool(row.get("Is_Reactivado") == 1 or "reactivad" in str(row.get("Consulta_Detalle", "")).lower() or "[respuesta]" in str(row.get("Consulta_Detalle", "")).lower())
    if is_reactivado:
        score += 20
        
    score = max(0, min(100, score))
    
    if "Descartado" in tags or "no desea" in str(row.get("Consulta_Detalle", "")).lower():
        estado = "🚫 Descartado"
    elif is_conv:
        estado = "🏆 Ganado / Derivado"
    elif score >= 60:
        estado = "🔥 Hot (Alta Prioridad)"
    elif score >= 40:
        estado = "⚡ Warm (En Seguimiento)"
    elif row.get("Remarketing") == 1:
        estado = "🔄 Remarketing"
    else:
        estado = "❄️ Cold (Baja Actividad)"
        
    return score, estado


def calculate_recontact_recommendation(row: pd.Series) -> Tuple[str, str, str]:
    """
    Motor de Recomendación de Recontacto Comercial:
    Analiza intención, estado, producto, días sin contacto e historial de toques salientes.
    Reglas de negocio:
    - Contactados Hoy (0 días): 🟢 Hablado Hoy (Protección anti-saturación de mensajes).
    - Inactividad ≥ 14 días (2 semanas o más): 🔴 Urgente (Reactivación comercial).
    - Inactividad entre 1 y 13 días: 🟡 En Seguimiento (Seguimiento activo en período normal).
    - Ganados / Derivados / Descartados: ⚪ No Requiere / Descartado.
    Retorna: (Prioridad, Accion_Sugerida, Motivo)
    """
    is_conv = bool(row.get("Convertido_Derivado") == 1 or str(row.get("Convertido_Derivado")).lower() == "true")
    tags = row.get("Intent_Tags", [])
    estado = str(row.get("Estado_Lead", ""))
    detail = str(row.get("Consulta_Detalle", "")).lower()
    score = int(row.get("Lead_Score", 30))
    prod = str(row.get("Linea_Producto", "")).strip()
    prod_label = prod if prod and prod != "Sin Especificar" else "Equipos"
    cant_cont = int(row.get("Cant_Contactos", 1))
    is_remarketing = bool(row.get("Remarketing") == 1)
    has_saliente = "wa saliente" in detail

    # Días sin contacto
    dias_sin_cont = row.get("Dias_Sin_Contacto")
    if dias_sin_cont is None or pd.isna(dias_sin_cont):
        dias_sin_cont = 999
    else:
        try:
            dias_sin_cont = int(dias_sin_cont)
        except Exception:
            dias_sin_cont = 999

    # 1. Lead ya convertido o ganado
    if is_conv or "🏆" in estado:
        return "⚪ No Requiere", "✅ Lead ya derivado / Ganado", "El prospecto ya fue derivado a closer para cierre comercial"

    # 2. Lead descartado / sin interés
    if "Descartado" in tags or "no desea" in detail or "🚫" in estado:
        return "⚪ Descartado", "🚫 No contactar (descartado)", "Cliente no interesado o fuera de perfil comercial"

    # 3. CONTACTADO HOY (0 días): Protección anti-saturación de mensajes en el mismo día
    if dias_sin_cont == 0:
        return (
            "🟢 Hablado Hoy",
            f"⏳ Contactado hoy: en espera de respuesta ({prod_label})",
            f"Ya se interactuó con el cliente hoy ({cant_cont} interacción(es)). Esperando feedback antes de reiterar contacto.",
        )

    # 4. URGENTES: 2 semanas o más sin contacto (≥ 14 días) o prospectos calientes sin atender
    if dias_sin_cont >= 14:
        dias_str = f"hace {dias_sin_cont} días" if dias_sin_cont < 900 else "más de 2 semanas sin contacto"
        return (
            "🔴 Urgente",
            f"📲 Recontactar por WhatsApp: reactivación comercial ({prod_label})",
            f"Sin interacción desde {dias_str} (≥2 semanas). Oportunidad prioritaria para reactivar y enviar propuesta actualizada.",
        )

    # 5. EN SEGUIMIENTO RECIENTE (1 a 13 días)
    if 1 <= dias_sin_cont < 14:
        return (
            "🟡 En Seguimiento",
            f"⏳ Seguimiento activo ({prod_label})",
            f"Último contacto hace {dias_sin_cont} día(s). En curso dentro de la ventana estándar de respuesta.",
        )

    # 6. Fallback de rutina
    return (
        "🟢 Rutina",
        f"📅 Enviar novedades o consulta de prospección ({prod_label})",
        "Lead de baja actividad / base general para nutrición",
    )


def generate_reactivation_message(
    row: pd.Series | Dict[str, Any],
    strategy: str = "short",
    variant_seed: Optional[int] = None
) -> str:
    """
    Generador dinámico de mensajes anti-bloqueo para reactivación comercial de prospectos fríos (Spintax).
    Estrategias:
    - 'short': Pregunta corta de 9 palabras (Dean Jackson) enfocada en curiosidad y respuesta simple sin fricción.
    - 'news': Aporte de valor con novedad de producto o caso de éxito zonal.
    - 'budget': Actualización de cotización, condiciones comerciales y financiación.
    - 'discard': Cierre por descarte amable para confirmar continuidad del proyecto.
    """
    import random
    if variant_seed is not None:
        rng = random.Random(variant_seed)
    else:
        raw_id = str(row.get("ID_Lead", row.get("Telefono", "123")))
        seed_val = abs(hash(str(raw_id) + str(strategy)))
        rng = random.Random(seed_val)

    name_raw = str(row.get("Contacto", "")).strip()
    clean_name = name_raw if name_raw and not any(k in name_raw.lower() for k in ["lead", "cliente", "whatsapp", "usuario", "-"]) else ""
    
    prod = str(row.get("Linea_Producto", "")).strip()
    if not prod or prod == "Sin Especificar":
        prod = "los equipos"
    
    loc = str(row.get("Localidad", "")).strip()
    prov = str(row.get("Provincia", "")).strip()
    zone = loc if (loc and loc != "Sin Localidad") else (prov if (prov and prov != "Otras Provincias") else "")

    # Variantes de Saludo con Spintax
    saludos = [
        f"Hola {clean_name}" if clean_name else "Hola",
        f"¡Hola {clean_name}! ¿Cómo estás?" if clean_name else "¡Hola! ¿Cómo estás?",
        f"Buenas {clean_name}" if clean_name else "Buenas",
        f"Qué tal {clean_name}, buen día" if clean_name else "Qué tal, buen día",
        f"Hola {clean_name}, un gusto saludarte" if clean_name else "Hola, un gusto saludarte",
    ]
    saludo = rng.choice(saludos).strip()

    # Estrategia 1: SHORT (Pregunta corta de 9 palabras)
    if strategy == "short":
        if "davis" in prod.lower():
            cuerpos = [
                "¿todavía estás buscando una estación meteorológica para tu campo?",
                "¿aún estás evaluando incorporar una estación Davis?",
                "¿seguís interesado en el monitoreo del clima para tu lote?",
            ]
        elif "sentek" in prod.lower():
            cuerpos = [
                "¿todavía estás buscando sondas de humedad para el suelo?",
                "¿aún estás evaluando optimizar el riego y monitoreo de suelo?",
                "¿seguís interesado en las sondas de humedad Sentek?",
            ]
        elif "jardin" in prod.lower():
            cuerpos = [
                "¿todavía estás buscando equipamiento o automatización de riego para tu jardín?",
                "¿aún estás interesado en los equipos de riego para tu parque?",
            ]
        elif "raphael" in prod.lower() or "valvul" in prod.lower():
            cuerpos = [
                "¿todavía estás buscando válvulas hidráulicas para tu instalación?",
                "¿aún estás evaluando las válvulas de control para tu proyecto?",
            ]
        else:
            cuerpos = [
                f"¿todavía estás evaluando incorporar {prod} para tu proyecto?",
                f"¿seguís con interés en las soluciones de {prod}?",
            ]
        cuerpo = rng.choice(cuerpos)
        return f"{saludo}! {cuerpo.strip()}"

    # Estrategia 2: NEWS (Novedad técnica / Caso de éxito)
    elif strategy == "news":
        zone_str = f" en la zona de {zone}" if zone else ""
        if "davis" in prod.lower():
            textos = [
                f"Te escribo del equipo de Abatech. Acabamos de armar un reporte técnico de rendimiento de estaciones Davis{zone_str} y me acordé de tu consulta. ¿Te gustaría que te lo comparta por acá?",
                f"Te contacto de Abatech porque ingresó stock nuevo de estaciones Davis con calibración actualizada. ¿Querés que te pase la ficha técnica y opciones disponibles para tu campo?",
            ]
        elif "sentek" in prod.lower():
            textos = [
                f"Te escribo de Abatech porque estamos compartiendo los resultados de manejo de riego con sondas Sentek{zone_str}. ¿Querés que te pase el resumen técnico?",
                f"Te contacto de Abatech para comentarte que tenemos disponible la nueva guía de calibración de sondas de humedad Sentek. ¿Te gustaría que te la envíe?",
            ]
        else:
            textos = [
                f"Te escribo de Abatech porque sumamos novedades y soporte técnico para {prod}{zone_str}. ¿Te gustaría que revisemos juntos si aplica a tu proyecto actual?",
                f"Te contacto del equipo técnico de Abatech. Estuvimos actualizando especificaciones para {prod}. ¿Querés que te comparta los detalles?",
            ]
        return f"{saludo}! {rng.choice(textos)}"

    # Estrategia 3: BUDGET (Actualización de Presupuesto & Financiación)
    elif strategy == "budget":
        textos = [
            f"Te contacto de Abatech para comentarte que abrimos nuevas condiciones de financiación y listas actualizadas para {prod}. ¿Te gustaría que revisemos tu cotización anterior para optimizar los números?",
            f"Te escribo de Abatech ya que estamos renovando propuestas comerciales de {prod} con facilidades de pago para esta etapa. ¿Querés que te reenvíe el presupuesto actualizado?",
            f"Desde Abatech queríamos acercarte las opciones de compra vigentes para {prod}. Si aún estás planificando la inversión, ¿te gustaría coordinar una cotización a medida?",
        ]
        return f"{saludo}! {rng.choice(textos)}"

    # Estrategia 4: DISCARD (Cierre por descarte / Filtro amable)
    elif strategy == "discard":
        textos = [
            f"Te escribo brevemente desde Abatech. Entiendo que estuviste con mucho trabajo, así que solo quería confirmar si preferís que pausemos tu consulta por {prod} o si todavía tenés previsto evaluarlo para esta campaña.",
            f"Te contacto de Abatech para saber si seguimos adelante con tu consulta de {prod} o si por el momento decidieron no avanzar. ¡Así actualizamos nuestro registro y no te molestamos!",
            f"Quería consultarte si aún tienen en carpeta el proyecto de {prod} o si preferís que lo dejemos en pausa para más adelante. Cualquier novedad estamos a disposición.",
        ]
        return f"{saludo}! {rng.choice(textos)}"

    # Fallback
    return f"{saludo}! ¿Cómo estás? Te contacto del equipo de Abatech para retomar el contacto por {prod}. ¿Pudiste avanzar con tu proyecto o te gustaría que revisemos los detalles técnicos y presupuesto actualizado?"


def get_daily_reactivation_batch(df: pd.DataFrame, batch_size: int = 20) -> pd.DataFrame:
    """
    Selecciona y ordena el lote diario de prospectos fríos prioritarios para reactivar hoy.
    Criterios de selección segura y priorizada:
    1. No convertidos (Convertido_Derivado == 0)
    2. No descartados (Estado_Lead != 🚫 Descartado)
    3. Con teléfono válido (no vacío)
    4. Sin contacto en el día de hoy (Dias_Sin_Contacto > 0)
    5. Prioriza prospectos con tiempo sin contacto (>= 14 días o fríos/urgentes).
    6. Ordenados por Lead_Score (descendente) y Dias_Sin_Contacto (descendente).
    """
    if df.empty:
        return df.copy()

    # Filtro base de candidatos válidos
    tel_series = df.get("Telefono", pd.Series("", index=df.index)).astype(str).str.strip()
    estado_series = df.get("Estado_Lead", pd.Series("", index=df.index)).astype(str)
    conv_series = pd.to_numeric(df.get("Convertido_Derivado", 0), errors="coerce").fillna(0)
    dias_series = pd.to_numeric(df.get("Dias_Sin_Contacto", 999), errors="coerce").fillna(999)

    mask = (
        (conv_series == 0) &
        (~estado_series.str.contains("Descartado|Ganado", case=False, na=False)) &
        (tel_series.str.len() >= 6) &
        (dias_series > 0)
    )
    
    candidates = df[mask].copy()
    if candidates.empty:
        return candidates

    # Filtrar preferentemente los fríos o urgentes (>= 14 días)
    cand_dias = pd.to_numeric(candidates.get("Dias_Sin_Contacto", 999), errors="coerce").fillna(999)
    cand_estado = candidates.get("Estado_Lead", pd.Series("", index=candidates.index)).astype(str)
    cand_prio = candidates.get("Recontacto_Prioridad", pd.Series("", index=candidates.index)).astype(str)

    frios_mask = (
        (cand_dias >= 14) |
        (cand_estado.str.contains("Cold|Frío", case=False, na=False)) |
        (cand_prio.str.contains("Urgente|Rutina", case=False, na=False))
    )
    
    selected = candidates[frios_mask]
    if selected.empty:
        selected = candidates

    sort_cols = [c for c in ["Lead_Score", "Dias_Sin_Contacto"] if c in selected.columns]
    if sort_cols:
        selected = selected.sort_values(by=sort_cols, ascending=[False, False])

    return selected.head(batch_size).reset_index(drop=True)


def build_whatsapp_link(phone: str, name: str = "", product: str = "", custom_text: str = "") -> str:
    """
    Construye un enlace oficial y directo de WhatsApp (wa.me) con saludo personalizado.
    Normaliza prefijos argentinos a formato internacional 549...
    """
    import urllib.parse
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return ""
        
    if digits.startswith("549") and len(digits) >= 12:
        clean = digits
    elif digits.startswith("54") and len(digits) >= 11:
        clean = "549" + digits[2:]
    elif len(digits) == 10:
        clean = "549" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        clean = "549" + digits[1:]
    else:
        clean = "549" + digits if len(digits) >= 8 else digits

    if len(clean) < 8:
        return ""

    if custom_text:
        msg = custom_text
    else:
        name_clean = name.strip() if name and "lead" not in name.lower() and "whatsapp" not in name.lower() else ""
        greeting = f"Hola {name_clean}" if name_clean else "Hola"
        prod_clean = product.strip() if product and product != "Sin Especificar" else ""
        prod_text = f" respecto a tu consulta por {prod_clean}" if prod_clean else ""
        msg = f"{greeting}! ¿Cómo estás? Te contacto del equipo de Abatech para retomar el contacto{prod_text}. ¿Pudiste avanzar con tu proyecto o te gustaría que revisemos juntos los detalles técnicos y presupuesto actualizado?"

    return f"https://wa.me/{clean}?text={urllib.parse.quote(msg)}"



def load_and_enrich_leads(file_path: Optional[str | Path | Any] = None) -> Dict[str, pd.DataFrame]:
    """
    Carga y enriquece completamente todas las hojas de Leeds orden.xlsx con variables de Data Science:
    - Enriquecimiento geográfico preciso (Provincia, Localidad, Región).
    - Cadencia temporal (Cantidad de contactos, Lead Age, Días en pipeline, Fechas inicio y fin).
    - NLP Intent Tags.
    - Lead Score (0-100) y Segmento.
    - Prioridad de Recontacto y Acción Sugerida.
    - Enlace directo a WhatsApp (wa.me).
    """
    cfg = get_config()
    if file_path is None or file_path == "Leeds orden.xlsx":
        source = cfg.resolve_leads_path()
    elif isinstance(file_path, (str, Path)):
        source = Path(file_path)
    else:
        source = file_path

    if isinstance(source, Path) and not source.exists():
        logger.warning(f"Archivo de leads no encontrado en: {source}")
        return {}

    try:
        excel_sheets = pd.read_excel(source, sheet_name=None)
        logger.info(f"Cargado dataset de leads desde '{source}' ({len(excel_sheets)} hojas)")
    except Exception as e:
        logger.error(f"Error al leer archivo Excel de leads '{source}': {e}", exc_info=True)
        return {}
    enriched_sheets: Dict[str, pd.DataFrame] = {}

    for s_name, raw_df in excel_sheets.items():
        if raw_df.empty:
            continue
            
        df = raw_df.copy()
        
        if s_name == "Leeds":
            rename_map = {
                'remarketing 01/06/26': 'Remarketing',
                'Unnamed: 1': 'Convertido_Derivado',
                'Unnamed: 2': 'Calificado',
                'NUMERO': 'ID_Lead',
                'NOMBRE': 'Contacto',
                'PRODUCTO': 'Telefono',
                'PRODUCTO.1': 'Linea_Producto',
                'CONSULTA ': 'Consulta_Detalle'
            }
            df = df.rename(columns=rename_map)
        else:
            cols_map = {}
            for col in df.columns:
                c_str = str(col).strip()
                if c_str == "True" or c_str == "False" or "Unnamed: 0" in c_str:
                    cols_map[col] = "Convertido_Derivado"
                elif c_str.isdigit() or c_str in ["NUMERO", "ID"]:
                    cols_map[col] = "ID_Lead"
                elif any(k in c_str.lower() for k in ["nombre", "cliente", "contacto"]):
                    cols_map[col] = "Contacto"
                elif any(k in c_str.lower() for k in ["telefono", "teléfono", "celular", "producto"]) and "producto.1" not in c_str.lower():
                    cols_map[col] = "Telefono"
                elif "producto.1" in c_str.lower() or c_str in ["Sentek", "Davis", "Jardineria", "Raphael"]:
                    cols_map[col] = "Linea_Producto"
                elif "consulta" in c_str.lower() or "detalle" in c_str.lower():
                    cols_map[col] = "Consulta_Detalle"
                    
            df = df.rename(columns=cols_map)

        if "Linea_Producto" not in df.columns or df["Linea_Producto"].isna().all():
            if s_name in ["Sentek", "Davis", "Jardineria", "Rapahel"]:
                df["Linea_Producto"] = s_name
            else:
                df["Linea_Producto"] = "Sin Especificar"
                
        df["Linea_Producto"] = df["Linea_Producto"].apply(clean_product_line)

        if "Contacto" in df.columns:
            df["Contacto"] = df["Contacto"].apply(sanitize_display_name)

        # Enriquecimiento Geográfico
        if "Telefono" in df.columns:
            geos = df["Telefono"].apply(extract_geo_from_phone)
            df["Provincia"] = [g[0] for g in geos]
            df["Localidad"] = [g[1] for g in geos]
            df["Region"] = [g[2] for g in geos]
        else:
            df["Provincia"] = "Otras Provincias"
            df["Localidad"] = "Sin Localidad"
            df["Region"] = "Otras Regiones"

        # Cadencia y Fechas de Contacto
        date_cols = [c for c in df.columns if str(c).upper().startswith("FECHA CONTACTO")]
        
        now_dt = datetime.datetime.now()
        today_midnight = pd.Timestamp(now_dt).floor("D")

        if date_cols:
            df_dates_only = df[date_cols].apply(pd.to_datetime, errors="coerce")
            summary_count = df_dates_only.notna().sum(axis=1)
            if "CANT_CONTACTOS_TOTAL" in df.columns:
                stored_count = pd.to_numeric(df["CANT_CONTACTOS_TOTAL"], errors="coerce").fillna(0)
                summary_count = pd.concat([summary_count, stored_count], axis=1).max(axis=1)
            df["Cant_Contactos"] = summary_count
            df["Cant_Contactos"] = df["Cant_Contactos"].apply(lambda x: max(1, int(x) if pd.notna(x) else 1))
            df["Fecha_Primer_Contacto"] = df_dates_only.min(axis=1)
            df["Fecha_Ultimo_Contacto"] = df_dates_only.max(axis=1)
            if "FECHA_PRIMER_CONTACTO_CRM" in df.columns:
                df["Fecha_Primer_Contacto"] = pd.to_datetime(df["FECHA_PRIMER_CONTACTO_CRM"], errors="coerce").fillna(df["Fecha_Primer_Contacto"])
            if "FECHA_ULTIMO_CONTACTO_CRM" in df.columns:
                df["Fecha_Ultimo_Contacto"] = pd.to_datetime(df["FECHA_ULTIMO_CONTACTO_CRM"], errors="coerce").fillna(df["Fecha_Ultimo_Contacto"])
            
            diff_days = (today_midnight - df["Fecha_Ultimo_Contacto"].dt.floor("D")).dt.days
            df["Dias_Sin_Contacto"] = diff_days.fillna(999).astype(int)
            df["Dias_Sin_Contacto"] = df["Dias_Sin_Contacto"].apply(lambda d: 0 if d < 0 else int(d))
            
            df["Dias_En_Pipeline"] = (df["Fecha_Ultimo_Contacto"] - df["Fecha_Primer_Contacto"]).dt.days.fillna(0).astype(int)
            df["Mes_Ingreso"] = df["Fecha_Primer_Contacto"].dt.strftime("%Y-%m").fillna(now_dt.strftime("%Y-%m"))
        else:
            df["Cant_Contactos"] = 1
            df["Fecha_Primer_Contacto"] = pd.NaT
            df["Fecha_Ultimo_Contacto"] = pd.NaT
            df["Dias_Sin_Contacto"] = 999
            df["Dias_En_Pipeline"] = 0
            df["Mes_Ingreso"] = now_dt.strftime("%Y-%m")

        def _format_ultimo_contacto_lbl(dias: int) -> str:
            if dias == 0:
                return "🟢 Hoy"
            elif dias == 1:
                return "🟡 Ayer (1 día)"
            elif 2 <= dias < 14:
                return f"🟡 Hace {dias} días"
            elif 14 <= dias < 900:
                return f"🔴 Hace {dias} días (≥2 sem)"
            else:
                return "⚪ Sin contacto reciente"

        df["Ultimo_Contacto_Label"] = df["Dias_Sin_Contacto"].apply(_format_ultimo_contacto_lbl)

        if "Convertido_Derivado" in df.columns:
            df["Convertido_Derivado"] = df["Convertido_Derivado"].apply(lambda x: 1 if (x is True or x == 1 or str(x).lower() == "true") else 0)
        else:
            df["Convertido_Derivado"] = 1 if "Derivados" in s_name else 0

        if "Remarketing" in df.columns:
            df["Remarketing"] = df["Remarketing"].apply(lambda x: 1 if (x is True or x == 1 or str(x).lower() == "true") else 0)
        else:
            df["Remarketing"] = 0

        if "Consulta_Detalle" in df.columns:
            df["Intent_Tags"] = df["Consulta_Detalle"].apply(extract_intent_tags)
            df["Tag_Principal"] = df["Intent_Tags"].apply(lambda tags: tags[0] if tags else "General")
        else:
            df["Intent_Tags"] = [["General"]] * len(df)
            df["Tag_Principal"] = "General"

        def _check_reactivado(row_ser: pd.Series) -> int:
            detail_str = str(row_ser.get("Consulta_Detalle", "")).lower()
            has_saliente = "wa saliente" in detail_str
            has_resp = "respuesta" in detail_str or ("[respuesta]" in detail_str) or ("reactivad" in detail_str)
            if (has_saliente and has_resp) or row_ser.get("Reactivado") == 1 or str(row_ser.get("Reactivado")).lower() == "true":
                return 1
            return 0

        df["Is_Reactivado"] = df.apply(_check_reactivado, axis=1)

        scores_estados = df.apply(calculate_lead_score, axis=1)
        df["Lead_Score"] = [s[0] for s in scores_estados]
        df["Estado_Lead"] = [s[1] for s in scores_estados]

        recontact_recs = df.apply(calculate_recontact_recommendation, axis=1)
        df["Recontacto_Prioridad"] = [r[0] for r in recontact_recs]
        df["Accion_Sugerida"] = [r[1] for r in recontact_recs]
        df["Motivo_Recontacto"] = [r[2] for r in recontact_recs]

        # Enlace directo para abrir chat de WhatsApp
        df["WhatsApp_Link"] = [
            build_whatsapp_link(
                phone=row.get("Telefono", ""),
                name=str(row.get("Contacto", "")),
                product=str(row.get("Linea_Producto", "")),
            )
            for _, row in df.iterrows()
        ]

        for str_col in ["Contacto", "Telefono", "Consulta_Detalle", "Provincia", "Localidad", "Region", "Estado_Lead", "Linea_Producto", "Recontacto_Prioridad", "Accion_Sugerida", "Motivo_Recontacto", "WhatsApp_Link", "Ultimo_Contacto_Label"]:
            if str_col in df.columns:
                df[str_col] = df[str_col].fillna("").astype(str)

        enriched_sheets[s_name] = df

    return enriched_sheets


def compute_lead_kpis(df: pd.DataFrame) -> LeadKPISummary:
    """Calcula los KPIs consolidados del dataset de leads."""
    total = len(df)
    if total == 0:
        return LeadKPISummary(0, 0, 0.0, 0, 0.0, 0.0, 0, 0, 0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0)

    convertidos = int((df["Convertido_Derivado"] == 1).sum()) if "Convertido_Derivado" in df.columns else 0
    tasa_conv = (convertidos / total * 100) if total > 0 else 0.0
    remarketing = int((df["Remarketing"] == 1).sum()) if "Remarketing" in df.columns else 0
    pct_rem = (remarketing / total * 100) if total > 0 else 0.0
    prom_cont = float(df["Cant_Contactos"].mean()) if "Cant_Contactos" in df.columns else 1.0
    hot = int((df["Estado_Lead"] == "🔥 Hot (Alta Prioridad)").sum()) if "Estado_Lead" in df.columns else 0
    warm = int((df["Estado_Lead"] == "⚡ Warm (En Seguimiento)").sum()) if "Estado_Lead" in df.columns else 0
    cold = int((df["Estado_Lead"] == "❄️ Cold (Baja Actividad)").sum()) if "Estado_Lead" in df.columns else 0
    dias_pipe = float(df["Dias_En_Pipeline"].mean()) if "Dias_En_Pipeline" in df.columns else 0.0

    contactados_hoy = int((df["Recontacto_Prioridad"].str.contains("Hoy", na=False) | (df.get("Dias_Sin_Contacto", 999) == 0)).sum()) if "Recontacto_Prioridad" in df.columns else 0
    recontacto_urg = int((df["Recontacto_Prioridad"] == "🔴 Urgente").sum()) if "Recontacto_Prioridad" in df.columns else 0
    en_seguimiento = int((df["Recontacto_Prioridad"].str.contains("Seguimiento", na=False) | (df["Recontacto_Prioridad"] == "🟡 Media")).sum()) if "Recontacto_Prioridad" in df.columns else 0
    recontacto_sug = recontacto_urg + en_seguimiento
    descartados = int((df["Estado_Lead"] == "🚫 Descartado").sum()) if "Estado_Lead" in df.columns else 0

    # Métricas de Reactivación
    frios_reactivables = int((
        (df.get("Convertido_Derivado", 0) == 0) &
        (~df.get("Estado_Lead", "").astype(str).str.contains("Descartado|Ganado", case=False, na=False)) &
        (df.get("Telefono", "").astype(str).str.strip().str.len() >= 6) &
        (df.get("Dias_Sin_Contacto", 999) >= 14)
    ).sum()) if not df.empty else 0

    leads_reactivados = int(df.get("Is_Reactivado", 0).sum()) if "Is_Reactivado" in df.columns else 0
    den = frios_reactivables + leads_reactivados
    tasa_reactivacion = (leads_reactivados / den * 100) if den > 0 else 0.0
    lote_diario_count = min(20, frios_reactivables)

    return LeadKPISummary(
        total_leads=total,
        convertidos=convertidos,
        tasa_conversion_pct=tasa_conv,
        remarketing_total=remarketing,
        pct_remarketing=pct_rem,
        promedio_contactos=prom_cont,
        leads_hot=hot,
        leads_warm=warm,
        leads_cold=cold,
        dias_promedio_pipeline=dias_pipe,
        recontacto_sugerido=recontacto_sug,
        recontacto_urgente=recontacto_urg,
        descartados=descartados,
        contactados_hoy=contactados_hoy,
        en_seguimiento=en_seguimiento,
        total_frios_reactivables=frios_reactivables,
        leads_reactivados=leads_reactivados,
        tasa_reactivacion_pct=tasa_reactivacion,
        lote_diario_count=lote_diario_count,
    )


def compute_product_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula métricas de rendimiento por línea de producto."""
    empty_cols = ["Linea_Producto", "Total_Leads", "Convertidos", "Remarketing", "Promedio_Contactos", "Score_Promedio", "Tasa_Conversion_Pct"]
    if df.empty or "Linea_Producto" not in df.columns:
        return pd.DataFrame(columns=empty_cols)
        
    res = (
        df.groupby("Linea_Producto", as_index=False)
        .agg(
            Total_Leads=("ID_Lead", "count"),
            Convertidos=("Convertido_Derivado", lambda x: (x == 1).sum()),
            Remarketing=("Remarketing", lambda x: (x == 1).sum()),
            Promedio_Contactos=("Cant_Contactos", "mean"),
            Score_Promedio=("Lead_Score", "mean"),
        )
    )
    res["Tasa_Conversion_Pct"] = (res["Convertidos"] / res["Total_Leads"] * 100).round(1)
    res["Promedio_Contactos"] = res["Promedio_Contactos"].round(2)
    res["Score_Promedio"] = res["Score_Promedio"].round(1)
    return res.sort_values(by="Total_Leads", ascending=False).reset_index(drop=True)


def compute_regional_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula métricas de geomarketing por región."""
    empty_cols = ["Region", "Total_Leads", "Convertidos", "Promedio_Contactos", "Score_Promedio", "Tasa_Conversion_Pct"]
    if df.empty or "Region" not in df.columns:
        return pd.DataFrame(columns=empty_cols)
        
    res = (
        df.groupby("Region", as_index=False)
        .agg(
            Total_Leads=("ID_Lead", "count"),
            Convertidos=("Convertido_Derivado", lambda x: (x == 1).sum()),
            Promedio_Contactos=("Cant_Contactos", "mean"),
            Score_Promedio=("Lead_Score", "mean"),
        )
    )
    res["Tasa_Conversion_Pct"] = (res["Convertidos"] / res["Total_Leads"] * 100).round(1)
    res["Promedio_Contactos"] = res["Promedio_Contactos"].round(2)
    res["Score_Promedio"] = res["Score_Promedio"].round(1)
    return res.sort_values(by="Total_Leads", ascending=False).reset_index(drop=True)


def compute_province_performance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el Ranking de Provincias de Argentina por volumen de leads,
    tasa de conversión y score promedio a partir del código de área.
    """
    empty_cols = ["Ranking", "Provincia", "Region", "Total_Leads", "Convertidos", "Promedio_Contactos", "Score_Promedio", "Porcentaje_Base_Pct", "Tasa_Conversion_Pct"]
    if df.empty or "Provincia" not in df.columns:
        return pd.DataFrame(columns=empty_cols)

    total_leads = len(df)
    res = (
        df.groupby("Provincia", as_index=False)
        .agg(
            Region=("Region", lambda x: x.mode().iloc[0] if not x.empty else "Otras Regiones"),
            Total_Leads=("ID_Lead", "count"),
            Convertidos=("Convertido_Derivado", lambda x: (x == 1).sum()),
            Promedio_Contactos=("Cant_Contactos", "mean"),
            Score_Promedio=("Lead_Score", "mean"),
        )
    )
    res = res.sort_values(by="Total_Leads", ascending=False).reset_index(drop=True)
    res.insert(0, "Ranking", range(1, len(res) + 1))
    res["Porcentaje_Base_Pct"] = ((res["Total_Leads"] / total_leads) * 100).round(1)
    res["Tasa_Conversion_Pct"] = ((res["Convertidos"] / res["Total_Leads"]) * 100).round(1)
    res["Promedio_Contactos"] = res["Promedio_Contactos"].round(2)
    res["Score_Promedio"] = res["Score_Promedio"].round(1)
    return res


@dataclass
class MeetingKPISummary:
    total_reuniones_derivaciones: int
    meets_agendados: int
    derivados_closers: int
    fichas_tecnicas: int
    superficie_total_ha: float
    total_cultivos_relevados: int
    closers_activos_count: int


def extract_meetings_and_technical_leads(df_leads: pd.DataFrame, df_opps: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Extrae, analiza y estructura todos los prospectos que cuentan con reuniones agendadas (Meet, Zoom, llamadas),
    derivaciones a closers (Jony, Luisa, Sergio, etc.) o relevamientos agronómicos (Hectáreas, Cultivos, Riego).
    """
    if df_leads.empty:
        return pd.DataFrame()

    records = []
    
    # Mapeo de oportunidades comerciales si están disponibles
    opps_by_contact: Dict[str, Dict[str, Any]] = {}
    if df_opps is not None and not df_opps.empty:
        for _, opp in df_opps.iterrows():
            c_name = str(opp.get("Cliente", "")).strip().lower()
            c_phone = re.sub(r"\D", "", str(opp.get("Contacto", "")))
            if c_name and c_name != "nan":
                opps_by_contact[c_name] = opp.to_dict()
            if len(c_phone) >= 8:
                opps_by_contact[c_phone[-8:]] = opp.to_dict()

    crop_dict = {
        "Papa": ["papa", "papas"],
        "Maíz": ["maiz", "maíz", "choclo"],
        "Soja": ["soja"],
        "Trigo": ["trigo"],
        "Ajo": ["ajo", "ajos"],
        "Cebolla & Zanahoria": ["cebolla", "zanahoria", "horticol", "hortícol"],
        "Olivos": ["olivo", "olivos", "aceituna"],
        "Cerezas": ["cereza", "cerezas"],
        "Nogales / Pecán": ["nogal", "nogales", "pecan", "pecán", "nuez"],
        "Kiwi": ["kiwi"],
        "Vid & Uva": ["vid", "uva", "viñedo", "bodega"],
        "Yerba Mate": ["yerba", "yerba mate"],
        "Berries / Moras": ["mora", "frambuesa", "arandano", "arándano"],
        "Secano Extensivo": ["secano"],
        "Maní": ["mani", "maní"],
        "Huertas": ["huerta", "bancal", "bancales", "vivero"],
    }

    tech_dict = {
        "Pívot Central": ["pivot", "pívot", "pivote"],
        "Riego por Goteo": ["goteo"],
        "Microaspersión": ["microaspersion", "microaspersión"],
        "Aspersión": ["aspersion", "aspersión"],
        "Sonda Sentek 120 cm": ["120 cm", "120cm", "120"],
        "Sonda Sentek 60 cm": ["60 cm", "60cm"],
        "Sonda Sentek 30 cm": ["30 cm", "30cm"],
        "TriSCAN (Salinidad)": ["triscan", "salinidad", "conductividad"],
        "Estación Davis Vantage Pro2": ["vantage pro", "pro 2", "pro2"],
        "Estación Davis Vantage Vue": ["vantage vue", "vue"],
        "Válvulas de Alivio Raphael": ["valvula", "válvula", "alivio", "hidraul"],
        "Caudalímetro": ["caudal", "caudalimetro", "caudalímetro"],
    }

    for _, row in df_leads.iterrows():
        txt = str(row.get("Consulta_Detalle", ""))
        nom = sanitize_display_name(str(row.get("Contacto", "Cliente")).strip())
        tel = str(row.get("Telefono", "")).strip()
        tel_digits = re.sub(r"\D", "", tel)
        prod = str(row.get("Linea_Producto", "Equipos")).strip()
        lead_id = row.get("ID_Lead", "")
        prov = str(row.get("Provincia", "Argentina"))
        loc = str(row.get("Localidad", "Sin Localidad"))
        score = int(row.get("Lead_Score", 30))
        ultimo_lbl = str(row.get("Ultimo_Contacto_Label", "Sin contacto"))

        # Chequear cruce con Comercial.xlsx
        matched_opp = opps_by_contact.get(nom.lower(), None)
        if not matched_opp and len(tel_digits) >= 8:
            matched_opp = opps_by_contact.get(tel_digits[-8:], None)

        opp_comments = str(matched_opp.get("Comentarios_Tecnicos", "")) if matched_opp else ""
        opp_derivado = str(matched_opp.get("Derivado_A", "")) if matched_opp else ""
        full_text = f"{txt} | {opp_comments} | {opp_derivado}"

        # 1. Detección de Reunión / Meet / Derivación
        is_meet = bool(re.search(r"\b(meet|zoom|reuni[oó]n|llamada|cordinar\s*reuni)\b", full_text, re.I))
        is_closer = bool(re.search(r"\b(jony|jonathan|luisa|sergio|alon|celina|agustina)\b", full_text, re.I)) or bool(row.get("Convertido_Derivado") == 1)
        has_ha = bool(re.search(r"(\d+[\d\.,]*)\s*(?:ha|has|hect[aá]reas|hectarea|hs\s+de\s+secano)", full_text, re.I))

        # Detectar cultivos
        found_crops = []
        for c_name, keywords in crop_dict.items():
            if any(re.search(r"\b" + kw, full_text, re.I) for kw in keywords):
                found_crops.append(c_name)

        # Si no tiene nada de reunión, ni closer ni hectáreas, descartar
        if not (is_meet or is_closer or has_ha or (found_crops and len(found_crops) > 0 and score >= 40)):
            continue

        # Clasificación del Tipo de Evento
        if is_meet:
            tipo_evento = "Meet / Zoom Agendado"
        elif is_closer:
            tipo_evento = "Derivación a Closer"
        else:
            tipo_evento = "Dossier Técnico / Campo"

        # 2. Extracción de Hectáreas
        ha_num = 0.0
        ha_str = "-"
        ha_matches = re.findall(r"(\d+[\d\.,]*)\s*(?:ha|has|hect[aá]reas|hectarea|hs\s+de\s+secano)", full_text, re.I)
        if ha_matches:
            raw_val = ha_matches[0].replace(".", "").replace(",", ".")
            try:
                ha_num = float(raw_val)
                ha_str = f"{int(ha_num):,} ha" if ha_num >= 1 else f"{ha_num:.1f} ha"
            except Exception:
                ha_str = f"{ha_matches[0]} ha"

        # 3. Extracción de Closer
        closer_match = re.findall(r"\b(jony|jonathan|luisa|sergio|alon|celina|agustina)\b", full_text, re.I)
        if closer_match:
            c_raw = closer_match[0].capitalize()
            closer_asignado = "Jony" if c_raw in ["Jony", "Jonathan"] else c_raw
        elif opp_derivado and opp_derivado != "nan":
            closer_asignado = opp_derivado.split()[0].capitalize()
        else:
            closer_asignado = "Equipo Técnico"

        # 4. Extracción de Tecnología / Riego
        found_tech = []
        for t_name, keywords in tech_dict.items():
            if any(re.search(r"\b" + kw, full_text, re.I) for kw in keywords):
                found_tech.append(t_name)
        tech_str = ", ".join(found_tech) if found_tech else (prod if prod != "Sin Especificar" else "Monitoreo")

        # 5. Resumen del Acuerdo / Notas de la Reunión
        if is_meet and "14 hs" in full_text:
            acuerdo = "Horario confirmado: 14:00 hs"
        elif "gustavocervantes992@gmail.com" in full_text:
            acuerdo = "Confirmó email para envío de cotización formal"
        elif "celina" in full_text.lower():
            acuerdo = "Meet agendado con Celina"
        elif ha_num >= 500:
            acuerdo = f"Cuenta estratégica de gran escala ({ha_str})"
        elif is_closer:
            acuerdo = f"Asignado a {closer_asignado} para presentación y cotización"
        elif is_meet:
            acuerdo = "Reunión / Meet solicitada para asesoramiento técnico"
        else:
            acuerdo = "Ficha agronómica con requerimientos específicos"

        wa_link = build_whatsapp_link(tel, nom, prod)

        records.append({
            "ID_Lead": lead_id,
            "Contacto": nom,
            "Telefono": tel,
            "Linea_Producto": prod,
            "Tipo_Evento": tipo_evento,
            "Closer": closer_asignado,
            "Superficie": ha_str,
            "Superficie_Num": ha_num,
            "Cultivos": ", ".join(found_crops) if found_crops else "General / Suelo",
            "Cultivo_Principal": found_crops[0] if found_crops else "General",
            "Tecnologia_Riego": tech_str,
            "Acuerdo_Reunion": acuerdo,
            "Provincia": prov,
            "Localidad": loc,
            "Lead_Score": score,
            "Ultimo_Contacto": ultimo_lbl,
            "WhatsApp_Link": wa_link,
            "Detalle_Completo": txt,
        })

    df_res = pd.DataFrame(records)
    if not df_res.empty:
        df_res = df_res.sort_values(by=["Superficie_Num", "Lead_Score"], ascending=[False, False]).reset_index(drop=True)
    return df_res


def compute_meeting_kpis(df_meetings: pd.DataFrame) -> MeetingKPISummary:
    """Calcula las métricas consolidadas del panel de reuniones y fichas técnicas."""
    total = len(df_meetings)
    if total == 0:
        return MeetingKPISummary(0, 0, 0, 0, 0.0, 0, 0)

    meets = int((df_meetings["Tipo_Evento"].str.contains("Meet|Zoom", na=False)).sum())
    closers = int((df_meetings["Tipo_Evento"].str.contains("Closer|Derivaci", na=False)).sum())
    fichas = int((df_meetings["Tipo_Evento"].str.contains("Dossier|Técnico", na=False)).sum())
    
    superficie_total = float(df_meetings["Superficie_Num"].sum()) if "Superficie_Num" in df_meetings.columns else 0.0
    
    cultivos_set = set()
    for c in df_meetings.get("Cultivos", []):
        for item in str(c).split(","):
            val = item.strip()
            if val and val != "General / Suelo" and val != "-":
                cultivos_set.add(val)
                
    closers_set = set(df_meetings.get("Closer", []).dropna().unique()) - {"Equipo Técnico", "-"}

    return MeetingKPISummary(
        total_reuniones_derivaciones=total,
        meets_agendados=meets,
        derivados_closers=closers,
        fichas_tecnicas=fichas,
        superficie_total_ha=superficie_total,
        total_cultivos_relevados=len(cultivos_set),
        closers_activos_count=len(closers_set),
    )

