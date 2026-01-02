"""
Gestor de CRM en Notion para trackear colegios contactados.
Registra información de cada colegio al que se envía la presentación.
"""
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

try:
    from notion_client import Client
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    logger.warning("notion-client no está instalado. Instala con: pip install notion-client")


class NotionCRMManager:
    """
    Gestor de CRM en Notion para registrar colegios contactados.
    
    Estructura de la base de datos en Notion:
    - School Name (title): Nombre del colegio
    - Email (email): Email de contacto
    - School ID (rich_text): Identificador único del colegio (roll number u otro)
    - County (select): Condado
    - City Zone (select): Zona de Dublin (si aplica)
    - Education Level (select): primary/secondary
    - Contact Date (date): Fecha de primer contacto
    - Status (select): contacted, followed_up, interested, not_interested, hired
    - Sender Email (email): Email del remitente
    - Notes (rich_text): Notas adicionales
    - Last Updated (last_edited_time): Auto-gestionado por Notion
    """
    
    def __init__(self, api_key: Optional[str] = None, database_id: Optional[str] = None):
        """
        Inicializa el gestor de Notion CRM.
        
        Args:
            api_key: Token de integración de Notion (o usa NOTION_API_KEY del .env)
            database_id: ID de la base de datos de Notion (o usa NOTION_DATABASE_ID del .env)
        """
        if not NOTION_AVAILABLE:
            raise ImportError("notion-client no está instalado. Instala con: pip install notion-client")
        
        self.api_key = api_key or os.getenv('NOTION_API_KEY')
        self.database_id = database_id or os.getenv('NOTION_DATABASE_ID')
        
        if not self.api_key:
            raise ValueError("NOTION_API_KEY no está configurado")
        if not self.database_id:
            raise ValueError("NOTION_DATABASE_ID no está configurado")
        
        self.client = Client(auth=self.api_key)
        logger.info("✅ Cliente de Notion inicializado correctamente")
    
    def add_school_contact(
        self,
        school_name: str,
        email: str,
        school_id: str = "",
        county: str = "",
        dublin_zone: str = "",
        education_level: str = "Primary",
        sender_email: str = "",
        notes: str = "",
        status: str = "Contacted"
    ) -> Optional[str]:
        """
        Añade un nuevo contacto de colegio al CRM de Notion.
        
        Args:
            school_name: Nombre del colegio
            email: Email del colegio
            school_id: Identificador único (roll number)
            county: Condado
            dublin_zone: Zona de Dublin si aplica
            education_level: Nivel educativo (primary/secondary)
            sender_email: Email del remitente
            notes: Notas adicionales
            status: Estado inicial (contacted por defecto)
        
        Returns:
            ID de la página creada en Notion o None si falla
        """
        try:
            # Verificar si ya existe un registro para este email
            existing = self._find_school_by_email(email)
            if existing:
                logger.info(f"Colegio {school_name} ({email}) ya existe en Notion CRM. Actualizando...")
                return self.update_school_contact(
                    page_id=existing['id'],
                    notes=notes,
                    contact_date=datetime.now().isoformat(),
                    status=status
                )
            
            # Crear propiedades de la página pero sólo incluir las que existen
            db_props = self._get_database_properties()

            properties = {}
            if "School Name" in db_props:
                properties["School Name"] = {"title": [{"text": {"content": school_name}}]}
            if "Email" in db_props:
                properties["Email"] = {"email": email}
            if "Status" in db_props:
                properties["Status"] = {"select": {"name": status}}
            if "Contact Date" in db_props:
                properties["Contact Date"] = {"date": {"start": datetime.now().isoformat()}}
            
            # Añadir campos opcionales solo si tienen valor
            if school_id and "School ID" in db_props:
                properties["School ID"] = {"rich_text": [{"text": {"content": school_id}}]}
            
            if county and "County" in db_props:
                properties["County"] = {"select": {"name": county.title()}}
            
            if dublin_zone and "City Zone" in db_props:
                properties["City Zone"] = {"select": {"name": dublin_zone}}
            
            if education_level and "Education Level" in db_props:
                properties["Education Level"] = {"select": {"name": education_level}}
            
            if sender_email and "Sender Email" in db_props:
                properties["Sender Email"] = {"email": sender_email}
            
            if notes and "Notes" in db_props:
                properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
            
            # Crear página en Notion
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            page_id = response.get('id')
            logger.info(f"✅ Colegio {school_name} añadido a Notion CRM (ID: {page_id})")
            return page_id
            
        except Exception as e:
            logger.error(f"❌ Error añadiendo colegio a Notion CRM: {e}")
            return None
    
    def update_school_contact(
        self,
        page_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        contact_date: Optional[str] = None
    ) -> Optional[str]:
        """
        Actualiza un registro existente en el CRM.
        
        Args:
            page_id: ID de la página en Notion
            status: Nuevo estado
            notes: Notas adicionales (se concatenan)
            contact_date: Nueva fecha de contacto
        
        Returns:
            ID de la página actualizada o None si falla
        """
        try:
            # Actualizar sólo propiedades existentes en la DB
            db_props = self._get_database_properties()
            properties = {}

            if status and "Status" in db_props:
                properties["Status"] = {"select": {"name": status}}

            if contact_date and "Contact Date" in db_props:
                properties["Contact Date"] = {"date": {"start": contact_date}}
            
            if notes and "Notes" in db_props:
                # Obtener notas existentes y concatenar
                existing_page = self.client.pages.retrieve(page_id=page_id)
                existing_notes = ""
                if "Notes" in existing_page["properties"]:
                    notes_content = existing_page["properties"]["Notes"].get("rich_text", [])
                    if notes_content:
                        existing_notes = notes_content[0].get("text", {}).get("content", "")
                
                new_notes = f"{existing_notes}\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {notes}" if existing_notes else notes
                properties["Notes"] = {"rich_text": [{"text": {"content": new_notes}}]}
            
            # Actualizar página
            response = self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            
            logger.info(f"✅ Registro actualizado en Notion CRM (ID: {page_id})")
            return response.get('id')
            
        except Exception as e:
            logger.error(f"❌ Error actualizando registro en Notion CRM: {e}")
            return None
    
    def _find_school_by_email(self, email: str) -> Optional[Dict]:
        """
        Busca un colegio por email en la base de datos.
        
        Args:
            email: Email del colegio
        
        Returns:
            Información de la página si existe, None si no
        """
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "Email",
                    "email": {"equals": email}
                }
            )
            
            results = response.get('results', [])
            if results:
                return results[0]
            return None
            
        except Exception as e:
            logger.error(f"❌ Error buscando colegio por email en Notion: {e}")
            return None

    def _get_database_properties(self) -> Dict:
        """Recupera las propiedades actuales de la base de datos en Notion.

        Devuelve un diccionario con las propiedades (las claves son los nombres de las columnas).
        """
        try:
            resp = self.client.databases.retrieve(database_id=self.database_id)
            props = resp.get('properties', {}) or {}
            return props
        except Exception as e:
            logger.error(f"❌ Error obteniendo esquema de la DB de Notion: {e}")
            return {}
    
    def get_all_contacts(self, status_filter: Optional[str] = None) -> List[Dict]:
        """
        Obtiene todos los contactos del CRM, opcionalmente filtrados por estado.
        
        Args:
            status_filter: Estado para filtrar (contacted, followed_up, etc.)
        
        Returns:
            Lista de contactos
        """
        try:
            query_params = {"database_id": self.database_id}
            
            if status_filter:
                query_params["filter"] = {
                    "property": "Status",
                    "select": {"equals": status_filter}
                }
            
            response = self.client.databases.query(**query_params)
            
            contacts = []
            for page in response.get('results', []):
                props = page['properties']
                
                contact = {
                    'id': page['id'],
                    'school_name': self._extract_title(props.get('School Name', {})),
                    'email': props.get('Email', {}).get('email', ''),
                    'school_id': self._extract_rich_text(props.get('School ID', {})),
                    'county': self._extract_select(props.get('County', {})),
                    'dublin_zone': self._extract_select(props.get('City Zone', {})),
                    'education_level': self._extract_select(props.get('Education Level', {})),
                    'status': self._extract_select(props.get('Status', {})),
                    'contact_date': self._extract_date(props.get('Contact Date', {})),
                    'sender_email': props.get('Sender Email', {}).get('email', ''),
                    'notes': self._extract_rich_text(props.get('Notes', {})),
                    'last_updated': page.get('last_edited_time', '')
                }
                contacts.append(contact)
            
            logger.info(f"✅ Obtenidos {len(contacts)} contactos del CRM")
            return contacts
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo contactos de Notion CRM: {e}")
            return []
    
    @staticmethod
    def _extract_title(prop: Dict) -> str:
        """Extrae texto de una propiedad tipo title."""
        title_content = prop.get('title', [])
        if title_content:
            return title_content[0].get('text', {}).get('content', '')
        return ''
    
    @staticmethod
    def _extract_rich_text(prop: Dict) -> str:
        """Extrae texto de una propiedad tipo rich_text."""
        rich_text = prop.get('rich_text', [])
        if rich_text:
            return rich_text[0].get('text', {}).get('content', '')
        return ''
    
    @staticmethod
    def _extract_select(prop: Dict) -> str:
        """Extrae valor de una propiedad tipo select."""
        select = prop.get('select')
        if select:
            return select.get('name', '')
        return ''

    @staticmethod
    def _extract_date(prop: Dict) -> str:
        """Extrae la fecha (start) de una propiedad tipo date, manejando None de forma segura."""
        date_val = prop.get('date')
        if isinstance(date_val, dict):
            return date_val.get('start', '') or ''
        return ''


def create_notion_database_schema() -> Dict:
    """
    Devuelve el esquema sugerido para la base de datos de Notion.
    Este esquema debe crearse manualmente en Notion o usando la API.
    
    Returns:
        Diccionario con la estructura de propiedades
    """
    return {
        "School Name": {"type": "title"},
        "Email": {"type": "email"},
        "School ID": {"type": "rich_text"},
        "County": {
            "type": "select",
            "options": ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Donegal", 
                       "Kerry", "Mayo", "Tipperary", "Clare", "Wexford", "Wicklow", 
                       "Kildare", "Meath", "Louth", "Kilkenny", "Sligo", "Westmeath", 
                       "Offaly", "Carlow", "Laois", "Roscommon", "Cavan", "Monaghan", 
                       "Longford", "Leitrim", "Other"]
        },
        "City Zone": {
            "type": "select",
            "options": ["Dublin 1", "Dublin 2", "Dublin 3", "Dublin 4", "Dublin 5", 
                       "Dublin 6", "Dublin 6W", "Dublin 7", "Dublin 8", "Dublin 9", 
                       "Dublin 10", "Dublin 11", "Dublin 12", "Dublin 13", "Dublin 14", 
                       "Dublin 15", "Dublin 16", "Dublin 17", "Dublin 18", "Dublin 20", 
                       "Dublin 22", "Dublin 24", "All Dublin", "Not Applicable"]
        },
        "Education Level": {
            "type": "select",
            "options": ["Pre-school", "Primary", "Secondary", "Further Education", 
                       "Special Education", "Multi-level"]
        },
        "Contact Date": {"type": "date"},
        "Status": {
            "type": "select",
            "options": ["Contacted", "Interested", "Proposal Sent", "Hired", 
                       "Not Interested", "No Response"]
        },
        "Sender Email": {"type": "email"},
        "Notes": {"type": "rich_text"}
    }
