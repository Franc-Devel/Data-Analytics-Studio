"""
Script integral para generar datasets sintéticos/ficticios totalmente interconectados
para Data Analytics Studio (Nexo Analytics Suite).

Permite navegar entre todos los módulos y comprobar la correlación de datos:
- Leads CRM (Leeds orden.xlsx / sample_leads.xlsx)
- Pauta y Cotizaciones Comerciales (Comercial.xlsx / sample_comercial.xlsx)
- Bandeja de Entrada e Historial WhatsApp (whatsapp_inbox / live_incoming_messages.json)
- Base de datos relacional SQLite (data/consultora_crm.db)
"""

from __future__ import annotations
import json
from pathlib import Path
import datetime
import pandas as pd
import numpy as np


def generate_sample_data(data_dir: Path | str = "data"):
    root_dir = Path(__file__).resolve().parent.parent
    target_dir = Path(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    leads_file = target_dir / "sample_leads.xlsx"
    comm_file = target_dir / "sample_comercial.xlsx"

    print("[1/5] Generando dataset interconectado de Leads CRM...")

    # Personajes y empresas ficticias interconectadas
    connected_leads = [
        {
            "id": 1,
            "nombre": "Juan Perez (Agro del Sur)",
            "phone": "+54 9 351 777-1234",
            "producto": "Davis",
            "closer": "Jony",
            "ciudad": "Cordoba",
            "consulta": "Interes en 3 estaciones meteorologicas Davis Vantage Pro2 para monitoreo de heladas en Cordoba. Derivado a Jony.",
            "monto": 280000,
            "prob": "80%",
            "estado": "Cotizado / En Negociacion",
            "days_ago": 4,
            "dias_contacto_1": 2,
            "cotizacion_nota": "Propuesta tecnica por 3 estaciones Davis Vantage enviada tras reunion.",
            "wa_in": "Hola Jony, recibimos la cotizacion de las estaciones Davis Vantage. Queriamos confirmar si el plazo de entrega es de 15 dias.",
            "wa_out": "Hola Juan! Exacto, stock garantizado y entrega dentro de 15 dias habiles tras confirmacion de orden.",
            "meet_nota": "Revision tecnica de sensores de viento y radiacion solar con equipo de campo.",
        },
        {
            "id": 2,
            "nombre": "Elena Gomez (Establecimiento El Trebol)",
            "phone": "+54 9 11 5555-4444",
            "producto": "Sentek",
            "closer": "Luisa",
            "ciudad": "Buenos Aires",
            "consulta": "Presupuesto de 4 sondas de humedad Sentek Drill & Drop para lote en Pergamino. Derivado a Luisa.",
            "monto": 450000,
            "prob": "100%",
            "estado": "Ganado / Aprobado",
            "days_ago": 12,
            "dias_contacto_1": 3,
            "cotizacion_nota": "Cotizacion de sondas Sentek aprobada formalmente. Coordinando despacho.",
            "wa_in": "Buenas tardes Luisa, transferimos el anticipo de las sondas Sentek. Te adjunto el comprobante bancario.",
            "wa_out": "Excelente Elena, pago acreditado. Ya coordinamos el despacho agronomico para el lunes.",
            "meet_nota": "Definicion de profundidad de instalacion (60cm y 90cm) con responsable tecnico.",
        },
        {
            "id": 3,
            "nombre": "Carlos Rodriguez (Vinedos & Bodegas Mendoza)",
            "phone": "+54 9 261 444-3322",
            "producto": "Raphael",
            "closer": "Sergio",
            "ciudad": "Mendoza",
            "consulta": "Requerimiento de valvulas reguladoras de presion Raphael para riego por goteo en Valle de Uco. Derivado a Sergio.",
            "monto": 320000,
            "prob": "70%",
            "estado": "En Evaluacion Tecnica",
            "days_ago": 18,
            "dias_contacto_1": 5,
            "cotizacion_nota": "Evaluacion hidraulica de valvulas de control Raphael en proceso con ingenieria.",
            "wa_in": "Sergio, revisamos la ficha tecnica de las valvulas Raphael. Queriamos ver si soportan presion variable en cabezal.",
            "wa_out": "Hola Carlos! Si, el diafragma reforzado tolera hasta 16 bar. Te paso las curvas en PDF.",
            "meet_nota": "Presentacion de memoria de calculo y pruebas en banco de ensayo.",
        },
        {
            "id": 4,
            "nombre": "Laura Diaz (Viveros del Litoral)",
            "phone": "+54 9 341 666-7788",
            "producto": "Jardineria",
            "closer": "Alon",
            "ciudad": "Rosario",
            "consulta": "Controladores de riego inteligente Galcon para invernaulos florales en Rosario. Derivado a Alon.",
            "monto": 95000,
            "prob": "90%",
            "estado": "Aceptado",
            "days_ago": 22,
            "dias_contacto_1": 8,
            "cotizacion_nota": "Presupuesto de programadores Galcon aceptado por gerencia de produccion.",
            "wa_in": "Alon, confirmamos la compra de los controladores Galcon. Enviamos los datos de facturacion.",
            "wa_out": "Perfecto Laura, factura emitida y envio despachado por encomienda.",
            "meet_nota": "Capacitacion de uso de la app movil Galcon Bluetooth con encargados de invernaulo.",
        },
        {
            "id": 5,
            "nombre": "Martin Alvarez (Cereales del Centro)",
            "phone": "+54 9 221 777-1122",
            "producto": "GSI",
            "closer": "Jony",
            "ciudad": "La Plata",
            "consulta": "Sistemas de termometria y aireacion GSI para plantas de acopio en Balcarce. Derivado a Jony.",
            "monto": 185000,
            "prob": "60%",
            "estado": "En Analisis",
            "days_ago": 30,
            "dias_contacto_1": 15,
            "cotizacion_nota": "Cotizacion de cableado termometrico GSI en revision por directorio.",
            "wa_in": "Jony, estamos evaluando los costos de instalacion del sistema GSI para la proxima cosecha.",
            "wa_out": "Hola Martin! Podemos bonificar la mano de obra de calibracion si cerramos antes de fin de mes.",
            "meet_nota": "Revision de planos estructurales de silos de 5.000 toneladas.",
        },
        {
            "id": 6,
            "nombre": "Sofia Romero (Semillero Santa Fe)",
            "phone": "+54 9 342 555-8899",
            "producto": "Sentek",
            "closer": "Luisa",
            "ciudad": "Santa Fe",
            "consulta": "Monitoreo continuo de napas freaticas y humedad con Sentek en campos de multiplicacion.",
            "monto": 310000,
            "prob": "75%",
            "estado": "Cotizado",
            "days_ago": 14,
            "dias_contacto_1": 6,
            "cotizacion_nota": "Propuesta de telemetria Sentek enviada.",
            "wa_in": "Luisa, consultamos compatibilidad de las sondas con nuestra plataforma de telemetria existente.",
            "wa_out": "Hola Sofia, las sondas entregan SDI-12 y Modbus estandar, son 100% integrables.",
            "meet_nota": "Demostracion en vivo de integracion API con software de gestion.",
        },
        {
            "id": 7,
            "nombre": "Lucas Fernandez (Agropecuaria Pampeana)",
            "phone": "+54 9 2954 44-5566",
            "producto": "Davis",
            "closer": "Sergio",
            "ciudad": "Santa Rosa",
            "consulta": "Renovacion de red de 5 estaciones meteorologicas Davis Vantage Vue en La Pampa.",
            "monto": 390000,
            "prob": "85%",
            "estado": "En Negociacion",
            "days_ago": 25,
            "dias_contacto_1": 10,
            "cotizacion_nota": "Propuesta por paquete de 5 estaciones con gateway celular WeatherLink.",
            "wa_in": "Sergio, nos llego la cotizacion del pack Davis. Nos parece competitiva la propuesta.",
            "wa_out": "Excelente Lucas! Incluye ademas 1 ano de suscripcion Pro a WeatherLink Cloud.",
            "meet_nota": "Coordinacion logistica de puntos de montaje en lotes agricolas.",
        },
        {
            "id": 8,
            "nombre": "Diego Martinez (Haras San Jorge)",
            "phone": "+54 9 2323 55-6677",
            "producto": "Jardineria",
            "closer": "Alon",
            "ciudad": "Lujan",
            "consulta": "Sistema de aspersion para pistas de salto y entrenamiento equino con Galcon.",
            "monto": 140000,
            "prob": "90%",
            "estado": "Aceptado",
            "days_ago": 16,
            "dias_contacto_1": 4,
            "cotizacion_nota": "Valvulas solenoides y programador Galcon cotizados.",
            "wa_in": "Hola Alon, queremos coordinar la fecha de inicio de obra para la pista principal.",
            "wa_out": "Hola Diego! El equipo tecnico esta disponible a partir del jueves proximo.",
            "meet_nota": "Inspeccion de presion y caudal en boca de pozo.",
        },
        {
            "id": 9,
            "nombre": "Abatech Test (Cliente Piloto)",
            "phone": "3512 38-3481",
            "producto": "Davis",
            "closer": "Jony",
            "ciudad": "Cordoba",
            "consulta": "Consulta inicial por estacion meteorologica Davis Vantage Pro2.",
            "monto": 150000,
            "prob": "80%",
            "estado": "En Seguimiento",
            "days_ago": 35,
            "dias_contacto_1": 20,
            "cotizacion_nota": "Demostracion piloto de estacion Davis en predio experimental.",
            "wa_in": "Buenas, queriamos consultar por el mantenimiento anual de la estacion Davis.",
            "wa_out": "Hola! Disponemos de servicio oficial y repuestos originales de fabrica.",
            "meet_nota": "Control preventivo de anemometro y pluviometro.",
        },
    ]

    # Generar más prospectos para volumen estadístico realista (total 30)
    extra_names = [
        ("Agustin Morales", "Citricola Concordia", "223", "Mar del Plata", "Sentek", "Luisa"),
        ("Valeria Benitez", "Bodega El Manantial", "261", "Mendoza", "Raphael", "Sergio"),
        ("Mariano Castro", "Agroservicios del Sur", "387", "Salta", "GSI", "Jony"),
        ("Camila Herrera", "Floricultura Platense", "221", "La Plata", "Jardineria", "Alon"),
        ("Patricio Rios", "Granja Avicola San Cayetano", "341", "Rosario", "Davis", "Sergio"),
        ("Gabriela Torres", "Estancia La Esmeralda", "381", "Tucuman", "Sentek", "Luisa"),
        ("Esteban Navarro", "Silos y Acopio Trenque Lauquen", "299", "Neuquen", "GSI", "Jony"),
        ("Florencia Medina", "Vivero Los Robles", "379", "Corrientes", "Jardineria", "Alon"),
    ]

    for idx, (pname, comp, code, city, prod, closer) in enumerate(extra_names, start=10):
        connected_leads.append({
            "id": idx,
            "nombre": f"{pname} ({comp})",
            "phone": f"+54 9 {code} {np.random.randint(2000, 8999)}-{np.random.randint(1000, 9999)}",
            "producto": prod,
            "closer": closer,
            "ciudad": city,
            "consulta": f"Requerimiento de tecnologia {prod} para instalacion en {city}. Derivado a {closer}.",
            "monto": int(np.random.randint(80, 400)) * 1000,
            "prob": f"{np.random.choice([50, 70, 80, 90])}%",
            "estado": "En Gestion",
            "days_ago": int(np.random.randint(5, 50)),
            "dias_contacto_1": int(np.random.randint(1, 15)),
            "cotizacion_nota": f"Presupuesto de {prod} remitido para evaluacion.",
            "wa_in": f"Hola! Solicitamos informacion y especificaciones de {prod}.",
            "wa_out": f"Hola {pname.split()[0]}! Te contacta {closer} de Nexo Analytics con la propuesta.",
            "meet_nota": f"Reunion comercial de presentacion y alcance de {prod}.",
        })

    # Construir DataFrame de Leads
    records_leads = []
    base_date = pd.Timestamp.now()
    for lead in connected_leads:
        dt_0 = base_date - pd.Timedelta(days=lead["days_ago"])
        dt_1 = base_date - pd.Timedelta(days=lead["dias_contacto_1"]) if lead["dias_contacto_1"] else pd.NaT

        records_leads.append({
            "remarketing 01/06/26": 0,
            "Unnamed: 1": 1 if lead["prob"] == "100%" else 0,
            "Unnamed: 2": 1,
            "NUMERO": lead["id"],
            "NOMBRE": lead["nombre"],
            "PRODUCTO": lead["phone"],
            "PRODUCTO.1": lead["producto"],
            "CONSULTA ": f"{lead['consulta']} | WA Saliente ({dt_0.strftime('%d/%m')}): [{lead['closer']}] {lead['wa_out'][:80]}",
            "FECHA CONTACTO": dt_0,
            "FECHA CONTACTO.1": dt_1,
            "FECHA CONTACTO.2": pd.NaT,
            "Cant_Contactos": 2 if pd.notna(dt_1) else 1,
            "CANT_CONTACTOS_TOTAL": 2 if pd.notna(dt_1) else 1,
        })

    df_leads = pd.DataFrame(records_leads)
    with pd.ExcelWriter(leads_file, engine="openpyxl") as writer:
        df_leads.to_excel(writer, sheet_name="Leeds", index=False)
    print(f"  * Creado Leads: {leads_file} ({len(df_leads)} registros interconectados)")

    # 2. Generar sample_comercial.xlsx con las mismas cotizaciones y clientes
    print("[2/5] Generando dataset de Pauta y Comercial interconectado...")
    with pd.ExcelWriter(comm_file, engine="openpyxl") as writer:
        resumen_data = {
            " ": ["Inversion Total ($)", "Alcance / Impresiones", "Conversaciones Iniciadas", "Costo por Conversacion Promedio ($)"],
            "Sentek total": [450000, 320000, 120, 3750],
            "Davis total": [380000, 290000, 95, 4000],
            "Galgon Ag (GSI) Total": [210000, 180000, 45, 4666],
            "Galcon Gar (jardineria) Total": [310000, 410000, 180, 1722],
            "Raphael (total)": [260000, 150000, 35, 7428],
        }
        pd.DataFrame(resumen_data).to_excel(writer, sheet_name="Resumen", index=False)

        months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio"]
        for m_idx, m in enumerate(months):
            m_rows = [
                [m.upper(), "Sentek", "Davis", "Galgon Ag (GSI)", "Galcon Gar (jardineria)", "Raphael", "TOTAL"],
                ["Inversion ($)", 65000 + m_idx * 1500, 54000 + m_idx * 1000, 30000, 44000, 37000, 230000 + m_idx * 2500],
                ["Impresiones", 45000, 41000, 25000, 58000, 21000, 190000],
                ["Clicks", 900, 750, 400, 1400, 350, 3800],
                ["Conversaciones", 18, 14, 6, 25, 5, 68],
                ["CPL ($)", 3611, 3857, 5000, 1760, 7400, 3382],
                ["", "", "", "", "", "", ""],
                ["Cliente", "Contacto", "Producto", "Monto Cotizado", "Prob Cierre", "Derivado a", "Comentarios"],
            ]
            # Incorporar cotizaciones de nuestros leads interconectados en cada mes
            for lead in connected_leads[:6]:
                m_rows.append([
                    lead["nombre"],
                    lead["phone"],
                    lead["producto"],
                    lead["monto"],
                    lead["prob"],
                    lead["closer"],
                    lead["cotizacion_nota"],
                ])
            df_m = pd.DataFrame(m_rows)
            df_m.to_excel(writer, sheet_name=m, index=False, header=False)

    print(f"  * Creado Comercial: {comm_file} ({len(months) + 1} hojas)")

    # 3. Sincronizar archivos por defecto en data/
    (target_dir / "Leeds orden.xlsx").write_bytes(leads_file.read_bytes())
    (target_dir / "Comercial.xlsx").write_bytes(comm_file.read_bytes())
    print("  * Sincronizados data/Leeds orden.xlsx y data/Comercial.xlsx")

    # 4. Generar whatsapp_inbox con los mismos clientes y chats
    print("[3/5] Generando bandeja de entrada WhatsApp interconectada...")
    inbox_dir = root_dir / "whatsapp_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    wa_messages = []
    wa_contacts = {}
    for idx, lead in enumerate(connected_leads[:8], start=1):
        msg_id_in = f"msg_wa_in_{lead['id']:03d}"
        msg_id_out = f"msg_wa_out_{lead['id']:03d}"
        t_in = (datetime.datetime.now() - datetime.timedelta(days=lead["days_ago"], hours=2)).isoformat()
        t_out = (datetime.datetime.now() - datetime.timedelta(days=lead["dias_contacto_1"], hours=1)).isoformat()

        wa_messages.append({
            "id": msg_id_in,
            "from": lead["phone"],
            "name": lead["nombre"],
            "body": lead["wa_in"],
            "timestamp": t_in,
            "unread": False,
            "is_from_me": False,
        })
        wa_messages.append({
            "id": msg_id_out,
            "from": lead["phone"],
            "name": lead["closer"],
            "body": lead["wa_out"],
            "timestamp": t_out,
            "unread": False,
            "is_from_me": True,
        })

        wa_contacts[lead["phone"]] = {
            "name": lead["nombre"],
            "product": lead["producto"],
            "closer": lead["closer"],
            "monto_cotizado": lead["monto"],
            "lead_score": 85 if lead["prob"] in ["80%", "90%", "100%"] else 65,
        }

    with (inbox_dir / "live_incoming_messages.json").open("w", encoding="utf-8") as f:
        json.dump(wa_messages, f, indent=2, ensure_ascii=False)

    with (inbox_dir / "contacts_cache.json").open("w", encoding="utf-8") as f:
        json.dump(wa_contacts, f, indent=2, ensure_ascii=False)

    # 5. Inicializar la base de datos relacional SQLite y sincronizar leads
    print("[4/5] Inicializando base de datos relacional y sincronizando leads...")
    try:
        from finance_app.db.session import init_db, get_db_session
        from finance_app.db.excel_sync import import_leads_excel_to_db
        from finance_app.db.crm_service import create_or_update_customer, create_opportunity, create_task, log_customer_activity

        init_db()
        with get_db_session() as session:
            c_cnt, u_cnt = import_leads_excel_to_db(session, leads_file, user_actor="admin")
            session.commit()
            print(f"  * Clientes sincronizados en SQL: {c_cnt} creados, {u_cnt} actualizados")

            # Crear oportunidades comerciales y tareas interconectadas
            for lead in connected_leads[:6]:
                cust, _ = create_or_update_customer(
                    session=session,
                    phone=lead["phone"],
                    full_name=lead["nombre"],
                    product_line=lead["producto"],
                    province=lead["ciudad"],
                    user_actor="admin",
                )
                prob_int = int(lead["prob"].replace("%", "")) if "%" in str(lead["prob"]) else 70
                opp = create_opportunity(
                    session=session,
                    customer_id=cust.id,
                    title=f"Propuesta {lead['producto']} - {lead['nombre']}",
                    product=lead["producto"],
                    amount_ars=float(lead["monto"]),
                    stage="COTIZADO" if prob_int >= 80 else "PROPUESTA",
                    probability_pct=prob_int,
                    notes=lead["cotizacion_nota"],
                    user_actor="admin",
                )
                due_dt = datetime.datetime.now() + datetime.timedelta(days=int(lead["id"]), hours=10)
                create_task(
                    session=session,
                    customer_id=cust.id,
                    title=f"Reunión de seguimiento con {lead['closer']}: {lead['meet_nota']}",
                    due_date=due_dt,
                    task_type="REUNION",
                    priority="ALTA" if prob_int >= 80 else "MEDIA",
                    opportunity_id=opp.id,
                    user_actor="admin",
                )
                log_customer_activity(
                    session=session,
                    customer_id=cust.id,
                    summary=f"Chat comercial con closer {lead['closer']}",
                    channel="WHATSAPP",
                    direction="OUTBOUND",
                    content=f"Entrante: {lead['wa_in'][:80]} | Saliente ({lead['closer']}): {lead['wa_out'][:80]}",
                )
            session.commit()
            print("  * Oportunidades comerciales y reuniones agendadas exitosamente en el CRM")
    except Exception as exc:
        print(f"  * Aviso en sync SQL: {exc}")

    print("[5/5] Interconexion total completada exitosamente.")


if __name__ == "__main__":
    generate_sample_data()
