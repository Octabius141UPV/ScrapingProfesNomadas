#!/usr/bin/env python3
"""
Envía una presentación de Profes Nómadas por email a colegios
obtenidos desde EducationPosts.ie según selección de condado/zona.

Se puede usar de forma independiente o invocado desde el bot.
"""
import os
import asyncio
import logging
from typing import List, Dict, Optional, Set
from dotenv import load_dotenv
import unicodedata

# Cargar variables de entorno
load_dotenv(override=True)

from src.scrapers.scraper_educationposts import EducationPosts, DUBLIN_ZONES, DUBLIN_DISTRICTS
from src.generators.email_sender import EmailSender
from src.utils.firebase_manager import get_presentation_recipients, mark_presentation_sent

try:
    from src.utils.notion_crm_manager import NotionCRMManager
    NOTION_CRM_AVAILABLE = True
except ImportError:
    NOTION_CRM_AVAILABLE = False

logger = logging.getLogger("presentation_sender")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")


def discover_presentation_pdf() -> Optional[str]:
    """Busca el PDF de presentación por variables/env y rutas comunes."""
    path = os.getenv("PRESENTATION_PDF_PATH")
    candidates = [
        path,
        "templates/ProfesNomadas_Presentacion.pdf",
        "templates/profesnomadas_presentation.pdf",
        "assets/ProfesNomadas_Presentacion.pdf",
        "assets/profesnomadas_presentation.pdf",
        # Candidatos comunes en docs/
        "docs/Profes Nómadas Presentation.pdf",
        "docs/Profes Nomadas Presentation.pdf",
        "docs/profes nomadas presentation.pdf",
        "docs/profesnomadas_presentation.pdf",
    ]
    for c in candidates:
        if c and os.path.exists(c) and c.lower().endswith(".pdf"):
            return c
    # Búsqueda flexible en docs/
    try:
        docs_dir = "docs"
        if os.path.isdir(docs_dir):
            import unicodedata
            def _norm(s: str) -> str:
                return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch)).lower()
            for name in os.listdir(docs_dir):
                full = os.path.join(docs_dir, name)
                if os.path.isfile(full) and name.lower().endswith('.pdf'):
                    n = _norm(name)
                    if 'profes' in n and 'nomadas' in n and 'present' in n:
                        return full
    except Exception:
        pass
    return None


def is_valid_email(addr: str) -> bool:
    bad = ("noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie")
    addr_l = (addr or "").lower()
    return addr and not any(b in addr_l for b in bad)


async def collect_offers(county_selection: str, dublin_zone: Optional[str] = None, level: str = "primary") -> List[Dict]:
    """Recoge ofertas según condado/zona con el scraper."""
    county_map = {"cork": "4", "dublin": "27", "all": ""}
    county_id = county_map.get(county_selection, "")

    offers: List[Dict] = []
    if county_selection == "dublin" and dublin_zone and dublin_zone != "all":
        districts = DUBLIN_ZONES.get(dublin_zone, [])
        for district_id in districts:
            scraper = EducationPosts(level=level, county_id=county_id, district_id=district_id)
            district_offers = await scraper.fetch_all()
            for off in district_offers:
                off['district'] = DUBLIN_DISTRICTS.get(district_id, district_id)
            offers.extend(district_offers)
            await asyncio.sleep(2)
    else:
        scraper = EducationPosts(level=level, county_id=county_id, district_id="")
        offers = await scraper.fetch_all()
    return offers


async def send_presentation_to_schools(user_data: Dict) -> Dict:
    """
    Envía la presentación a los emails de colegios en la región seleccionada.

    user_data requiere: 'county_selection'
    opcionales: 'email'/'resend_from_email', 'resend_api_key', 'dublin_zone', 'subject', 'body'
    """
    try:
        sender = EmailSender()
        
        # Inicializar Notion CRM si está disponible y configurado
        notion_crm = None
        if NOTION_CRM_AVAILABLE:
            try:
                notion_crm = NotionCRMManager()
                logger.info("✅ Notion CRM inicializado y listo para registrar contactos")
            except (ValueError, ImportError) as e:
                logger.warning(f"⚠️  Notion CRM no disponible: {e}")
        
        resend_api_key = user_data.get('resend_api_key') or os.getenv('RESEND_API_KEY')
        resend_from_email = (
            user_data.get('resend_from_email')
            or user_data.get('email')
            or os.getenv('RESEND_FROM_EMAIL')
        )
        if not resend_api_key:
            return {"success": False, "message": "Resend no está configurado. Define RESEND_API_KEY o pásalo en user_data."}
        if not resend_from_email:
            return {"success": False, "message": "Falta el remitente. Configura RESEND_FROM_EMAIL o proporciona 'email'/'resend_from_email'."}

        pdf_path = user_data.get('presentation_pdf') or discover_presentation_pdf()
        if not pdf_path:
            return {"success": False, "message": "No se encontró el PDF de presentación. Configura PRESENTATION_PDF_PATH o colócalo en templates/"}

        county_selection = user_data.get('county_selection', 'all')
        dublin_zone = user_data.get('dublin_zone')
        level = user_data.get('education_level', 'primary')

        logger.info(f"Recogiendo ofertas para county={county_selection}, zone={dublin_zone or 'N/A'}, level={level}")
        offers = await collect_offers(county_selection, dublin_zone, level)
        if not offers:
            return {"success": False, "message": "No se encontraron colegios/ofertas"}

        # Filtrar y deduplicar emails (único por colegio y email)
        BAD_MAILS = ("noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie")

        def _school_identifier(offer: Dict) -> str:
            roll_keys = ['roll_number', 'roll', 'rollno', 'roll_no', 'rollnumber', 'school_ref']
            for key in roll_keys:
                val = offer.get(key)
                if val:
                    return str(val).strip()
            name = offer.get('school') or offer.get('school_name') or ''
            return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').strip().lower()

        emails: List[Dict[str, str]] = []
        seen_emails: Set[str] = set()
        seen_schools: Set[str] = set()

        for off in offers:
            mail = (off.get('email') or '').strip()
            if not mail or any(b in mail.lower() for b in BAD_MAILS):
                continue
            school_name = off.get('school') or off.get('school_name') or 'School'
            school_id = _school_identifier(off)
            if school_id and school_id in seen_schools:
                continue
            if mail.lower() in seen_emails:
                continue
            seen_emails.add(mail.lower())
            if school_id:
                seen_schools.add(school_id)
            emails.append({
                'email': mail,
                'school_name': school_name,
                'school_id': school_id,
            })

        if not emails:
            return {"success": False, "message": "No hay emails válidos para enviar"}

        # Cargar plantillas de asunto y cuerpo
        def _read(path: str) -> Optional[str]:
            try:
                if path and os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        return f.read().strip()
            except Exception:
                pass
            return None

        subject = user_data.get('subject') or _read('templates/presentation_subject.txt') or "Presentation – Profes Nómadas"
        body_tmpl = user_data.get('body') or _read('templates/presentation_body.txt') or (
            "Dear {school_name} Team,\n\n"
            "We are Profes Nómadas, a service that helps schools streamline teacher applications and communication.\n\n"
            "Please find attached a short presentation with our details.\n\n"
            "Kind regards,\nProfes Nómadas"
        )

        # Enviar uno por uno
        # Excluir emails ya contactados
        already_sent: Set[str] = set()
        try:
            already_sent = get_presentation_recipients(resend_from_email)
        except Exception as exc:
            logger.warning(f"No se pudo consultar Firebase para presentaciones previas: {exc}")

        skipped = 0
        if already_sent:
            filtered = []
            for item in emails:
                if item['email'].lower() in already_sent:
                    skipped += 1
                    continue
                filtered.append(item)
            emails = filtered

        if not emails:
            return {
                "success": True,
                "total": 0,
                "sent": 0,
                "errors": [],
                "message": (
                    "Todos los colegios encontrados ya habían recibido la presentación anteriormente"
                    f" ({skipped} omitidos)."
                ),
                "pdf": pdf_path,
            }

        total = len(emails)
        sent = 0
        errors: List[str] = []
        for idx, item in enumerate(emails, 1):
            body = body_tmpl.format(school_name=item['school_name']) if '{school_name}' in body_tmpl else body_tmpl
            ok = await sender.send_presentation_email(
                from_email=resend_from_email,
                from_password=None,
                to_email=item['email'],
                presentation_pdf_path=pdf_path,
                subject=subject,
                body=body,
                resend_api_key=resend_api_key,
                resend_from_email=resend_from_email,
            )
            if ok:
                sent += 1
                logger.info(f"[{idx}/{total}] ✅ Enviado a {item['email']}")
                
                # Registrar en Firebase
                try:
                    mark_presentation_sent(
                        sender_email=resend_from_email,
                        recipient_email=item['email'].lower(),
                        data={
                            'school': item['school_name'],
                            'school_id': item['school_id'],
                        }
                    )
                except Exception as exc:
                    logger.warning(f"No se pudo registrar en Firebase el envío a {item['email']}: {exc}")
                
                # Registrar en Notion CRM
                if notion_crm:
                    try:
                        notion_crm.add_school_contact(
                            school_name=item['school_name'],
                            email=item['email'],
                            school_id=item['school_id'],
                            county=county_selection.title() if county_selection != 'all' else '',
                            dublin_zone=dublin_zone or '',
                            education_level=level,
                            sender_email=resend_from_email,
                            notes=f"Presentación enviada automáticamente",
                            status="contacted"
                        )
                        logger.info(f"📝 Registrado en Notion CRM: {item['school_name']}")
                    except Exception as exc:
                        logger.warning(f"No se pudo registrar en Notion CRM el envío a {item['email']}: {exc}")
            else:
                err = f"[{idx}/{total}] ❌ Falló {item['email']}"
                logger.error(err)
                errors.append(err)
            await asyncio.sleep(1)

        return {
            "success": True,
            "total": total,
            "sent": sent,
            "errors": errors,
            "pdf": pdf_path,
            "skipped": skipped,
        }
    except Exception as e:
        logger.exception("Error en envío de presentación")
        return {"success": False, "message": str(e)}


async def _main_cli():
    """Modo CLI simple para pruebas manuales."""
    user_data = {
        'email': os.getenv('EMAIL_ADDRESS'),
        'resend_api_key': os.getenv('RESEND_API_KEY'),
        'county_selection': os.getenv('PRESENTATION_COUNTY', 'all'),
        'dublin_zone': os.getenv('PRESENTATION_DUBLIN_ZONE'),
        'presentation_pdf': os.getenv('PRESENTATION_PDF_PATH'),
        'resend_from_email': os.getenv('RESEND_FROM_EMAIL'),
    }
    res = await send_presentation_to_schools(user_data)
    print(res)


if __name__ == "__main__":
    asyncio.run(_main_cli())
