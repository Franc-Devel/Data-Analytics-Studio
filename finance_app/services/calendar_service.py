"""
Nexo Analytics - Servicio de Integración con Calendario (iCalendar .ics)
Genera invitaciones y archivos de calendario estándar compatibles con Google Calendar, Outlook y Apple Calendar.
"""

from __future__ import annotations
import datetime
import uuid


def generate_meeting_ics(
    title: str,
    description: str,
    location: str,
    start_time: datetime.datetime,
    duration_minutes: int = 45,
    organizer_name: str = "Nexo Analytics · Consultoría",
    organizer_email: str = "consultoria@abatech.com.ar",
) -> str:
    """
    Genera un archivo iCalendar (.ics) estándar RFC 5545 para una reunión comercial.
    """
    end_time = start_time + datetime.timedelta(minutes=duration_minutes)
    
    # Formateo UTC
    dtstamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dtstart = start_time.strftime("%Y%m%dT%H%M%S")
    dtend = end_time.strftime("%Y%m%dT%H%M%S")
    uid = f"{uuid.uuid4()}@consultora.nexoanalytics.com"

    clean_summary = title.replace("\n", " ").replace(";", "\\;").replace(",", "\\,")
    clean_desc = description.replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")
    clean_loc = location.replace("\n", " ").replace(";", "\\;").replace(",", "\\,")

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nexo Analytics//CRM Commercial Suite//ES
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{clean_summary}
DESCRIPTION:{clean_desc}
LOCATION:{clean_loc}
STATUS:CONFIRMED
ORGANIZER;CN={organizer_name}:mailto:{organizer_email}
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Recordatorio de Reunión Comercial: {clean_summary}
END:VALARM
END:VEVENT
END:VCALENDAR"""

    return ics_content
