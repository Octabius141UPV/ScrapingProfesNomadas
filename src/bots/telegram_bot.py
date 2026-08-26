#!/usr/bin/env python3
"""
Bot de Telegram para gestionar documentos
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
from dotenv import load_dotenv
import json
from typing import Dict, Callable, List, Optional, Set
import aiofiles
import sys
import asyncio
from datetime import datetime
import unicodedata
import shutil
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import ssl
import re
import uuid
import functools

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.document_reader import DocumentReader
from src.utils.pdf_generator import PDFGenerator
from src.utils.document_validator import DocumentValidator
from src.scrapers.scraper_educationposts import EducationPosts
import traceback
from src.utils.firebase_manager import (
    get_applied_vacancies,
    mark_vacancy_as_applied,
    upload_file_to_storage,
    get_presentation_recipients,
    mark_presentation_sent,
)
from src.generators.email_sender import EmailSender
from src.utils.application_send_policy import ApplicationSendPolicy
from src.utils.application_delivery_queue import (
    ApplicationDeliveryQueue,
    DeliveryAttempt,
)
try:
    from src.utils.notion_crm_manager import NotionCRMManager
    _NOTION_CRM_AVAILABLE = True
except Exception:
    _NOTION_CRM_AVAILABLE = False

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID del usuario autorizado
AUTHORIZED_USER_IDS = [1070017515, 7034549850, 6334888548, 6386385237]

class UserData:
    def __init__(self):
        self.name = None
        self.email = None
        self.email_password = None  # Contraseña de aplicación para envío
        self.letter_of_application = None  # Texto de la Letter of Application
        self.teaching_placements = []  # Lista de teaching placements
        self.referees = []  # Lista de referees
        self.documents = {
            'letter_of_application': None,  # Letter of Application (obligatorio)
            'cv': None,  # CV (obligatorio)
            'degree': None,  # Título universitario (obligatorio)
            'application_form': None,  # Standard Application Form (obligatorio)
            'teaching_practice': None,  # Teaching Practice (obligatorio)
            'referees': None,  # Referees (obligatorio)
            'tc_registration': None,  # Certificado de registro TC (opcional)
            'religion_certificate': None  # Certificado de religión (opcional)
        }
        self.excel_profile = None  # Ruta al archivo Excel con el perfil
        self.chat_id = None
        self.state = None
        self.previous_state = None
        self.county_selection = None  # "cork", "dublin", "both"
        self.dublin_zone = None  # "north", "south", "west", "city_center", "all"
        self.education_level = None  # "primary", "post_primary", "pre_school", etc.
        self.education_level_id = None  # ID para el scraper
        self.referentes_sent = False  # Controla si ya se envió el Excel de referentes
        self.practicas_sent = False   # Controla si ya se envió el Excel de prácticas
        
        # Solo el atributo que realmente causa el error
        self.teaching_council_registration = None
        self.tc_route = None
        self.test_mode = False  # Nuevo atributo para el modo test
        self.presentation_mode = False  # Modo para enviar presentación de Profes Nómadas
        self.presentation_pdf = None

    def has_required_documents(self):
        """Verifica si se han enviado todos los documentos obligatorios"""
        return all([
            self.documents['letter_of_application'],
            self.documents['cv'],
            self.documents['degree'],
            self.documents['application_form'],
            self.documents['teaching_practice'],
            self.documents['referees']
        ])
        
    def has_required_form_data(self):
        """Verifica si se han completado los datos básicos del formulario"""
        # Solo verificamos nombre y correo electrónico
        return bool(self.name and self.email)

def normaliza_respuesta(respuesta: str) -> str:
    respuesta = respuesta.strip().lower()
    respuesta = ''.join(
        c for c in unicodedata.normalize('NFD', respuesta)
        if unicodedata.category(c) != 'Mn'
    )
    return respuesta

def es_respuesta_positiva(respuesta: str) -> bool:
    resp = normaliza_respuesta(respuesta)
    return resp in {"si", "sí", "s", "yes", "y"}

def es_respuesta_negativa(respuesta: str) -> bool:
    resp = normaliza_respuesta(respuesta)
    return resp in {"no", "n"}


TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def format_etb_exclusion_notice(
    count: int,
    school_names: List[str],
    max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> str:
    """Build a bounded ETB exclusion notice using unique public school names."""
    try:
        count = max(0, int(count))
    except (TypeError, ValueError):
        count = 0
    if not count:
        return ""

    unique_names = []
    for raw_name in school_names or []:
        name = " ".join(str(raw_name).split())
        if name and name not in unique_names:
            unique_names.append(name)

    prefix = f"⛔ Se ignoraron {count} ofertas de colegios ETB."
    suffix = " No se generarán PDFs ni se enviarán emails para ellas."
    if not unique_names:
        return (prefix + suffix)[:max_length]

    label = prefix + " Colegios: "
    visible_names = []
    for name in unique_names:
        candidate = label + ", ".join(visible_names + [name]) + "." + suffix
        if len(candidate) > max_length:
            break
        visible_names.append(name)

    omitted_count = len(unique_names) - len(visible_names)
    if omitted_count:
        marker = f" (+{omitted_count} nombres más)."
        while visible_names:
            candidate = (
                label
                + ", ".join(visible_names)
                + marker
                + suffix
            )
            if len(candidate) <= max_length:
                return candidate
            visible_names.pop()

        # This fallback is only relevant for unusually small custom limits;
        # Telegram's 4096-character limit leaves ample room for the normal
        # prefix, marker, and safety statement.
        compact = prefix + f" (+{omitted_count} nombres no mostrados)." + suffix
        return compact[:max_length]

    return label + ", ".join(visible_names) + "." + suffix


class TelegramBot:
    def __init__(self, token: str):
        """
        Inicializa el bot de Telegram
        
        Args:
            token: Token de autenticación del bot
        """
        # Asegurar variables de entorno disponibles cuando se invoquen comandos (/presentacion)
        try:
            load_dotenv(override=True)
        except Exception:
            pass
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Obtener lista de usuarios autorizados (usar la variable global o el .env)
        try:
            authorized_ids_env = os.getenv('AUTHORIZED_USER_IDS', '')
            if authorized_ids_env:
                # Usar regex para encontrar solo los números y convertirlos a int
                self.authorized_user_ids = [int(id_str) for id_str in re.findall(r'\d+', authorized_ids_env)]
            else:
                # Si no, usar la variable global definida al inicio
                self.authorized_user_ids = AUTHORIZED_USER_IDS
            
            logger.info(f"Usuarios autorizados: {self.authorized_user_ids}")
        except Exception as e:
            # En caso de error, usar un valor predeterminado para no romper el bot
            logger.error(f"Error al configurar usuarios autorizados: {e}")
            self.authorized_user_ids = [1070017515, 7034549850]
        self.user_data = {}  # Diccionario para almacenar datos de usuarios
        
        # Configurar manejadores de comandos
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("profesores", self.profesores_command))
        self.application.add_handler(CommandHandler("presentacion", self.presentation_command))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_county_selection, pattern="^(cork|dublin|ambos|toda irlanda)$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_dublin_zone_selection, pattern="^dublin_(1|2|3|4|5|6|6w|7|8|9|10|11|12|13|14|15|16|17|18|20|22|23|24|all)$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_education_level_selection, pattern="^(pre-school|primary|post-primary)$"))
        self.application.add_handler(CommandHandler("test", self.test_command))
        
        # Configurar manejador de errores
        self.application.add_error_handler(self.error_handler)
        
        # Inicializar validadores
        self.document_validator = DocumentValidator()
        self.pdf_generator = PDFGenerator()
        self.document_reader = DocumentReader()
        self.email_sender = EmailSender()
        self.send_policy = ApplicationSendPolicy()
        self._last_application_send_reason = None
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
        
        # Estado del scraping
        self.is_scraping = False
    
    def run(self):
        """Inicia el bot"""
        try:
            self.application.run_polling()
        except Exception as e:
            self.logger.error(f"Error al iniciar el bot: {e}")
            raise
    
    def stop(self):
        """Detiene el bot de forma segura"""
        try:
            self.application.stop()
        except Exception as e:
            self.logger.error(f"Error al detener el bot: {e}")
            raise
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start"""
        if not await self.is_authorized(update):
            return
        
        # Inicializar datos del usuario
        user_id = update.effective_user.id
        self.user_data[user_id] = UserData()
        self.user_data[user_id].chat_id = update.effective_chat.id
        
        welcome_message = (
            "👋 ¡Bienvenido al Bot de Scraping de EducationPosts!\n\n"
            "Comandos principales:\n"
            "• /presentacion – Enviar email de presentación con nuestro PDF\n"
            "• /profesores – Buscar ofertas y enviar aplicaciones\n\n"
            "Usa /help para ver la guía completa de documentos y reglas."
        )
        
        await update.message.reply_text(welcome_message)
    
    async def solicitar_nombre(self, update: Update):
        """Solicita el nombre del usuario."""
        user_id = update.effective_user.id
        user = self.user_data.get(user_id)
        if user:
            user.state = "waiting_name"
            await update.message.reply_text("Para comenzar, por favor, dime tu nombre completo:")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /help"""
        if not await self.is_authorized(update):
            return
        
        help_text = (
            "📚 **GUÍA DE DOCUMENTOS**\n\n"
            "Para que el sistema te permita continuar, **TODOS los documentos deben estar en formato PDF**.\n\n"
            "La **única excepción** es el **TC Registration**, que puede ser un archivo **PDF o una imagen** (JPG, PNG, etc.).\n\n"
            "El bot reconoce tus archivos por el nombre. Incluye estas palabras clave para que los identifique correctamente:\n\n"
            "📄 **Documentos Obligatorios (en formato PDF):**\n"
            "• `letter of application`, `carta`, `cover letter`\n"
            "• `cv`, `curriculum`, `resume`\n"
            "• `degree`, `titulo`, `certificate`, `diploma`\n"
            "• `application form`, `formulario`, `standard`\n"
            "• `teaching practice`, `practicas`, `placements`\n"
            "• `referees`, `references`, `referencia`\n\n"
            "📄 **Documentos Opcionales:**\n"
            "• Para `religion`, `religious`: solo **PDF**.\n"
            "• Para `tc registration`, `teaching council`: **PDF o Imagen**.\n\n"
            "💡 **Consejo:** Si el bot no reconoce un archivo, comprueba que el nombre del fichero contenga una de las palabras clave y que sea un PDF."
        )
        
        await update.message.reply_text(help_text)

    async def profesores_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Activa el modo de envío de aplicaciones a ofertas (profesores) y explica el flujo."""
        if not await self.is_authorized(update):
            return
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            self.user_data[user_id] = UserData()
            self.user_data[user_id].chat_id = update.effective_chat.id
        user = self.user_data[user_id]

        # Reset flags/estados de modo presentación
        user.presentation_mode = False

        texto = (
            "📚 Modo Profesores (envío a ofertas)\n\n"
            "Este modo te guía para reunir tus documentos, buscar ofertas y enviar tus aplicaciones.\n\n"
            "Pasos del flujo:\n"
            "1) Envía tus documentos requeridos (formato PDF): Letter of Application, CV, Degree, Application Form, Teaching Practice, Referees.\n"
            "   - Opcionales: Teaching Council Registration (PDF o imagen) y Religion Certificate (PDF).\n"
            "2) Indica tu nombre, email y contraseña de aplicación de Gmail (App Password).\n"
            "3) Selecciona condado y nivel educativo.\n"
            "4) El bot hará scraping de EducationPosts, analizará requerimientos y preparará adjuntos.\n"
            "5) Podrás simular/envíar. Si usas /test, el envío se redirige a un email de prueba, "
            "pero mantiene los lotes, pausas y el espaciado.\n\n"
            "Consejos:\n"
            "- Nombra bien tus archivos para que el bot los reconozca (letter of application, cv, degree, application form, teaching practice, referees).\n"
            "- El Application Form debe ser PDF para personalizar POSITION ADVERTISED, School y ROLL NUMBER automáticamente.\n"
        )
        await update.message.reply_text(texto)
        # A partir de aquí, iniciamos el flujo de datos personales del usuario
        user.state = "waiting_name"
        await update.message.reply_text("Para comenzar, por favor, dime tu nombre completo:")

    async def presentation_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia el flujo para enviar la presentación de Profes Nómadas a colegios."""
        if not await self.is_authorized(update):
            return
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            self.user_data[user_id] = UserData()
            self.user_data[user_id].chat_id = update.effective_chat.id
        user = self.user_data[user_id]

        # Verificar credenciales básicas (usar .env como fallback si faltan)
        if not getattr(user, 'email', None):
            env_email = (
                os.getenv('EMAIL_ADDRESS') or
                os.getenv('EMAIL_USER') or
                os.getenv('EMAIL')
            )
            if env_email:
                user.email = env_email
        if not getattr(user, 'email_password', None):
            env_password = (
                os.getenv('EMAIL_PASSWORD') or
                os.getenv('EMAIL_PASS')
            )
            if env_password:
                user.email_password = env_password

        if not user.email or not user.email_password:
            await update.message.reply_text(
                "Para enviar la presentación necesitas registrar tu email y contraseña de aplicación.\n"
                "Usa /start y completa Email y Contraseña de aplicación de Gmail."
            )
            return
        user.presentation_mode = True

        # Intentar detectar la presentación
        pdf_path = self._discover_presentation_pdf()
        if not pdf_path:
            await update.message.reply_text(
                "⚠️ No encontré el PDF de presentación.\n"
                "Coloca el archivo en templates/ProfesNomadas_Presentacion.pdf, o en docs/ (por ejemplo 'Profes Nómadas Presentation.pdf'),\n"
                "o configura la variable PRESENTATION_PDF_PATH en .env."
            )
        else:
            user.presentation_pdf = pdf_path

        # Pedir selección de condado
        keyboard = [
            [InlineKeyboardButton("Cork", callback_data="cork")],
            [InlineKeyboardButton("Dublin", callback_data="dublin")],
            [InlineKeyboardButton("Toda Irlanda", callback_data="toda irlanda")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📣 Envío de presentación de Profes Nómadas\n\n"
            "Selecciona el condado de destino:",
            reply_markup=reply_markup
        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja la recepción de documentos"""
        if not await self.is_authorized(update):
            return
        
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            await update.message.reply_text("❌ Error: Por favor, inicia el proceso con /start")
            return
        
        user = self.user_data[user_id]
        
        try:
            # Obtener el archivo
            file = await update.message.document.get_file()
            file_name = update.message.document.file_name.lower()
            
            # 1. Determinar el tipo de documento PRIMERO
            doc_type = None
            file_name_lower = file_name # Ya está en minúsculas
            
            # Mapeo de palabras clave a tipos de documento
            doc_keywords = {
                'letter_of_application': ['letter of application', 'letterofapplication'],
                'cv': ['cv', 'curriculum', 'resume'],
                'degree': ['degree', 'titulo', 'universidad', 'universitario'],
                'application_form': ['application form', 'formulario', 'template', 'applicationform'],
                'teaching_practice': ['teaching practice', 'practicas', 'practices', 'placement', 'teaching placement', 'placements'],
                'referees': ['referees', 'references', 'referentes', 'referencia'],
                'tc_registration': ['tc', 'registration', 'teaching council'],
                'religion_certificate': ['religion', 'religious', 'certificate']
            }
            
            # Buscar coincidencias en el nombre del archivo
            for doc_type_key, keywords in doc_keywords.items():
                if any(keyword in file_name_lower for keyword in keywords):
                    doc_type = doc_type_key
                    break
                    
            # Caso especial: "letter of application def adc" debe procesarse como Letter of Application
            if 'letter of application def adc' in file_name_lower or ('letter of application' in file_name_lower and 'def adc' in file_name_lower):
                doc_type = 'letter_of_application'
            
            # 2. AHORA, se valida el formato del archivo
            is_tc_registration = doc_type == 'tc_registration'
            is_pdf = file_name.lower().endswith('.pdf')
            is_image = any(file_name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.heic', '.webp'])

            if is_tc_registration:
                if not is_pdf and not is_image:
                    await update.message.reply_text("❌ Error: El documento 'TC Registration' debe ser un archivo PDF o una imagen (JPG, PNG).")
                    return
            else:
                # Si el tipo de documento es conocido pero no es PDF, se rechaza.
                # Si no es conocido (doc_type es None), se le notificará al usuario más abajo.
                if doc_type and not is_pdf:
                    await update.message.reply_text(f"❌ Error: El documento '{doc_type}' debe estar en formato PDF.")
                    return
            
            # Crear directorio temporal si no existe
            os.makedirs("temp", exist_ok=True)
            # Usar el nombre original del archivo para guardarlo, no la versión en minúsculas
            temp_path = os.path.join("temp", update.message.document.file_name)
            
            # Descargar el archivo
            await file.download_to_drive(temp_path)
            
            # 3. Se notifica al usuario y se guarda el estado
            # Mensaje especial para 'letter of application def adc'
            if 'letter of application def adc' in file_name_lower or ('letter of application' in file_name_lower and 'def adc' in file_name_lower):
                await update.message.reply_text(
                    "ℹ️ He identificado que el archivo 'Letter of Application def AdC' es una carta de presentación. "
                    "Lo procesaré como Letter of Application."
                )
            
            if doc_type:
                # Guardar el documento
                user.documents[doc_type] = {
                    'path': temp_path,
                    'filename': update.message.document.file_name
                }
                
                # Actualizar atributos adicionales para compatibilidad
                if doc_type == 'tc_registration':
                    user.teaching_council_registration = True
                    logger.info(f"Usuario {user_id} subió documento TC Registration, actualizando teaching_council_registration=True")
                    
                    # Si ya conocemos la ruta, usamos el mensaje dinámico. Si no, uno genérico.
                    if user.tc_route:
                        await update.message.reply_text(
                            f"My application for the Teaching Council number {user.tc_route} has already been submitted and is currently being processed."
                        )
                    else:
                        # Si no se conoce la ruta, se pide al usuario
                        user.state = "waiting_tc_route_from_doc"
                        await update.message.reply_text(
                            "✅ Documento de TC Registration guardado. \n"
                            "Por favor, indica tu ruta de registro en el Teaching Council (1, 2, 3 o 4):"
                        )
                        # No continuamos con el resto de la lógica de handle_document hasta que se dé la ruta
                        return
                
                # Verificar documentos obligatorios faltantes
                missing_docs = []
                required_docs = {
                    'letter_of_application': "Letter of Application",
                    'cv': "CV",
                    'degree': "Título universitario (Degree)",
                    'application_form': "Standard Application Form",
                    'teaching_practice': "Teaching Practice",
                    'referees': "Referees"
                }
                
                for doc_key, doc_name in required_docs.items():
                    if not user.documents[doc_key]:
                        missing_docs.append(doc_name)
                
                if missing_docs:
                    # Comprobar documentos opcionales
                    optional_docs = []
                    if not user.documents['tc_registration']:
                        optional_docs.append("Teaching Council Registration")
                    if not user.documents['religion_certificate']:
                        optional_docs.append("Religious Education Certificate")
                    
                    # Construir mensaje
                    message = f"✅ {update.message.document.file_name} guardado correctamente.\n\n"
                    
                    if missing_docs:
                        message += "⚠️ Aún faltan los siguientes documentos OBLIGATORIOS:\n" + \
                            "\n".join(f"• {doc}" for doc in missing_docs) + \
                            "\n\nPor favor, envía los documentos faltantes."
                    
                    if optional_docs:
                        message += "\n\n📎 Documentos OPCIONALES que puedes enviar:\n" + \
                            "\n".join(f"• {doc}" for doc in optional_docs)
                    
                    await update.message.reply_text(message)
                else:
                    # Todos los documentos obligatorios recibidos, verificar opcionales
                    optional_docs = []
                    if not user.documents['tc_registration']:
                        optional_docs.append("Teaching Council Registration")
                    if not user.documents['religion_certificate']:
                        optional_docs.append("Religious Education Certificate")
                    
                    # Mostrar mensaje y botones para selección de condado
                    keyboard = [
                        [InlineKeyboardButton("Cork", callback_data="cork")],
                        [InlineKeyboardButton("Dublin", callback_data="dublin")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    message = "✅ Todos los documentos obligatorios han sido recibidos.\n"
                    
                    if optional_docs:
                        message += "\n📎 Recuerda que también puedes enviar estos documentos opcionales:\n" + \
                            "\n".join(f"• {doc}" for doc in optional_docs) + \
                            "\n\nPuedes enviarlos ahora o continuar con el proceso."
                    
                    message += "\n\nPor favor, selecciona el condado donde quieres buscar:"
                    
                    await update.message.reply_text(message, reply_markup=reply_markup)
                    user.state = "waiting_county"
            else:
                await update.message.reply_text(
                    "❌ Tipo de documento no reconocido.\n\n"
                    "El nombre del archivo debe contener alguna de estas palabras:\n"
                    "\n📝 DOCUMENTOS OBLIGATORIOS:\n"
                    "• Para Letter of Application: 'letter of application' o 'letterofapplication'\n"
                    "• Para CV: 'cv', 'curriculum' o 'resume'\n"
                    "• Para título universitario: 'degree', 'titulo', 'universidad' o 'universitario'\n"
                    "• Para Standard Application Form (.pdf): 'application form', 'formulario', 'standard' o 'template'\n"
                    "• Para Teaching Practice (.docx recomendado): 'teaching practice', 'practicas', 'practices' o 'placement'\n"
                    "• Para Referees (.docx recomendado): 'referees', 'references', 'referentes' o 'referencia'\n"
                    "\n📎 DOCUMENTOS OPCIONALES:\n"
                    "• Para certificado de registro TC: 'tc', 'registration' o 'teaching council'\n"
                    "• Para certificado de religión: 'religion', 'religious' o 'certificate'\n\n"
                    "IMPORTANTE: Se requiere formato .pdf para Application Form y se recomienda .docx para Teaching Practice y Referees Details para permitir la personalización automática con los datos de cada oferta.\n\n"
                    "Por favor, renombra el archivo e inténtalo de nuevo."
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error al procesar el documento: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto"""
        if not await self.is_authorized(update):
            return
        
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            self.user_data[user_id] = UserData()
            self.user_data[user_id].chat_id = update.effective_chat.id
        
        user = self.user_data[user_id]
        message_text = update.message.text
        
        if message_text.strip().lower() == "/atras":
            if user.previous_state:
                user.state, user.previous_state = user.previous_state, user.state
                await update.message.reply_text("Has vuelto al paso anterior. Por favor, responde de nuevo:")
                # Mostrar la pregunta correspondiente al estado actual
                if user.state == "waiting_name":
                    await update.message.reply_text("Por favor, envía tu nombre completo:")
                elif user.state == "waiting_email":
                    await update.message.reply_text("Por favor, envía tu email de contacto:")
                elif user.state == "waiting_email_password":
                    await update.message.reply_text("Por favor, envía tu contraseña de aplicación de Gmail:")
                elif user.state == "waiting_tc_registration":
                    await update.message.reply_text("¿Tienes registro en el Teaching Council? (Sí/No):")
                # Resto de estados eliminados ya que no se usan más
                else:
                    await update.message.reply_text("No puedes volver más atrás en este paso.")
            else:
                await update.message.reply_text("No puedes volver más atrás.")
            return
        
        if user.state == "waiting_name":
            user.name = message_text
            user.state = "waiting_email"
            await update.message.reply_text(
                "✅ Nombre guardado.\n\n"
                "Por favor, envía tu email de contacto:"
            )
        
        elif user.state == "waiting_email":
            user.email = message_text
            user.state = "waiting_email_password"
            await update.message.reply_text(
                "✅ Email guardado.\n\n"
                "Por favor, envía tu contraseña de aplicación de Gmail:"
            )
        
        elif user.state == "waiting_email_password":
            user.email_password = message_text
            user.state = "waiting_tc_registration"
            await update.message.reply_text(
                "✅ Contraseña guardada.\n\n"
                "¿Tienes registro en el Teaching Council? (Sí/No):"
            )
            
        elif user.state == "waiting_tc_registration":
            # Interpretar la respuesta de forma flexible
            if es_respuesta_positiva(message_text):
                tc_registration = True
            elif es_respuesta_negativa(message_text):
                tc_registration = False
            else:
                await update.message.reply_text("Por favor, responde 'sí' o 'no'.")
                return
            
            user.teaching_council_registration = tc_registration
            logger.info(f"Usuario {user_id} tiene TC registration: {tc_registration}")

            if tc_registration:
                user.state = "waiting_tc_route"
                await update.message.reply_text(
                    "✅ De acuerdo.\n\n"
                    "Por favor, indica tu ruta de registro en el Teaching Council (1, 2, 3 o 4):"
                )
            else:
                user.state = "waiting_documents"
                await update.message.reply_text(
                    "✅ Información básica guardada.\n\n"
                    "Ahora, por favor envía los documentos requeridos por EducationPosts.\n\n"
                    "📄 Documentos OBLIGATORIOS:\n"
                    "• Letter of Application (nombre debe contener 'letter of application', incluido 'letter of application def adc')\n"
                    "• CV (nombre debe contener 'cv')\n"
                    "• Título universitario (nombre debe contener 'degree')\n"
                    "• Application Form (.docx recomendado) (nombre debe contener 'application form')\n"
                    "• Teaching Practice (.docx recomendado) (nombre debe contener 'teaching practice')\n"
                    "• Referees (.docx recomendado) (nombre debe contener 'referees')\n\n"
                    "📄 Documentos OPCIONALES:\n"
                    "• Certificado de registro TC (nombre debe contener 'tc registration')\n"
                    "• Certificado de religión (nombre debe contener 'religion')\n\n"
                    "💡 IMPORTANTE: Se recomienda el formato .docx para Application Form, Teaching Practice y Referees Details para permitir la personalización automática con los datos de cada oferta.\n\n"
                    "ℹ️ NOTA ESPECIAL: El archivo 'Letter of Application def AdC' se procesará como Letter of Application."
                )

        elif user.state == "waiting_tc_route":
            route = message_text.strip()
            if route in ["1", "2", "3", "4"]:
                user.tc_route = route
                user.state = "waiting_documents"
                await update.message.reply_text(
                    f"✅ Ruta {route} guardada.\n\n"
                    "Ahora, por favor envía los documentos requeridos por EducationPosts.\n\n"
                    "📄 Documentos OBLIGATORIOS:\n"
                    "• Letter of Application (nombre debe contener 'letter of application', incluido 'letter of application def adc')\n"
                    "• CV (nombre debe contener 'cv')\n"
                    "• Título universitario (nombre debe contener 'degree')\n"
                    "• Application Form (.docx recomendado) (nombre debe contener 'application form')\n"
                    "• Teaching Practice (.docx recomendado) (nombre debe contener 'teaching practice')\n"
                    "• Referees (.docx recomendado) (nombre debe contener 'referees')\n\n"
                    "📄 Documentos OPCIONALES:\n"
                    "• Certificado de registro TC (nombre debe contener 'tc registration')\n"
                    "• Certificado de religión (nombre debe contener 'religion')\n\n"
                    "💡 IMPORTANTE: Se recomienda el formato .docx para Application Form, Teaching Practice y Referees Details para permitir la personalización automática con los datos de cada oferta.\n\n"
                    "ℹ️ NOTA ESPECIAL: El archivo 'Letter of Application def AdC' se procesará como Letter of Application."
                )
            else:
                await update.message.reply_text("❌ Ruta no válida. Por favor, introduce 1, 2, 3 o 4.")
        
        elif user.state == "waiting_tc_route_from_doc":
            route = message_text.strip()
            if route in ["1", "2", "3", "4"]:
                user.tc_route = route
                await update.message.reply_text(
                    f"✅ Ruta {route} guardada.\n\n"
                    f"My application for the Teaching Council number {route} has already been submitted and is currently being processed."
                )
                # Continuar con la verificación de documentos obligatorios
                missing_docs = []
                required_docs = {
                    'letter_of_application': "Letter of Application",
                    'cv': "CV", 
                    'degree': "Título universitario (Degree)",
                    'application_form': "Standard Application Form",
                    'teaching_practice': "Teaching Practice",
                    'referees': "Referees"
                }
                
                for doc_key, doc_name in required_docs.items():
                    if not user.documents[doc_key]:
                        missing_docs.append(doc_name)
                
                if missing_docs:
                    await update.message.reply_text(
                        f"Faltan documentos obligatorios:\n" + 
                        "\n".join(f"• {doc}" for doc in missing_docs) +
                        "\n\nPor favor, súbelos para continuar."
                    )
                    user.state = "waiting_documents"
                else:
                    # Todos los documentos obligatorios recibidos
                    keyboard = [
                        [InlineKeyboardButton("Cork", callback_data="cork")],
                        [InlineKeyboardButton("Dublin", callback_data="dublin")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "✅ Todos los documentos obligatorios han sido recibidos.\n\n"
                        "Por favor, selecciona el condado donde quieres buscar:",
                        reply_markup=reply_markup
                    )
                    user.state = "waiting_county"
            else:
                await update.message.reply_text("❌ Ruta no válida. Por favor, introduce 1, 2, 3 o 4.")
        
        elif user.state == "waiting_county":
            county = message_text.lower()
            if county in ["cork", "dublin"]:
                user.county_selection = county
                user.state = "waiting_education_level"
                await update.message.reply_text(
                    "✅ Condado seleccionado.\n\n"
                    "Por favor, selecciona el nivel educativo:\n"
                    "• Pre-school\n"
                    "• Primary\n"
                    "• Post-primary"
                )
            else:
                await update.message.reply_text(
                    "❌ Opción no válida. Por favor, selecciona:\n"
                    "• Cork\n"
                    "• Dublin"
                )
        
        elif user.state == "waiting_education_level":
            level = message_text.lower()
            if level in ["pre-school", "primary", "post-primary"]:
                user.education_level = level
                user.state = "ready"
                await update.message.reply_text(
                    "✅ Nivel educativo seleccionado.\n\n"
                    "🔍 Iniciando búsqueda de ofertas...\n"
                    "Este proceso puede tardar unos minutos."
                )
                # Aquí se iniciaría el proceso de scraping
            else:
                await update.message.reply_text(
                    "❌ Opción no válida. Por favor, selecciona:\n"
                    "• Pre-school\n"
                    "• Primary\n"
                    "• Post-primary"
                )
        
        elif user.state == "waiting_documents":
            # Enviar la plantilla del application form si el usuario la solicita
            if update.message.text.strip().lower() in ["/plantilla", "plantilla", "formulario", "application form"]:
                plantilla_path = "data/Application_Form_Template.pdf"
                if os.path.exists(plantilla_path):
                    await update.message.reply_document(document=plantilla_path, filename="Application_Form_Template.pdf")
                    await update.message.reply_text(
                        "📝 IMPORTANTE: Application Form Template\n\n"
                        "1. Descarga y rellena el formulario con tus datos personales.\n"
                        "2. ⭐️ GUÁRDALO EN FORMATO .PDF para que el sistema pueda personalizar automáticamente los campos:\n"
                        "   - POSITION ADVERTISED\n"
                        "   - School\n"
                        "   - ROLL NUMBER\n\n"
                        "3. Súbelo como documento adjunto manteniendo el formato .pdf.\n\n"
                        "👉 El sistema personalizará automáticamente tu PDF con los datos de cada oferta."
                    )
                else:
                    await update.message.reply_text("No se encontró la plantilla del Application Form. Contacta con el administrador.")
                return

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja errores del bot"""
        self.logger.error(f"Error en el bot: {context.error}")
        if update:
            await update.message.reply_text(
                "❌ Ha ocurrido un error. Por favor, intenta de nuevo más tarde."
            )
    
    async def is_authorized(self, update: Update) -> bool:
        """Verifica si el usuario está autorizado"""
        user_id = update.effective_user.id
        
        if user_id not in self.authorized_user_ids:
            logger.warning(f"Usuario no autorizado intentó usar el bot: {user_id}")
            await update.message.reply_text(
                "❌ No estás autorizado para usar este bot."
            )
            return False
        
        logger.info(f"Usuario autorizado: {user_id}")
        return True

    async def handle_county_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Error: Por favor, inicia el proceso con /start")
            return
        user = self.user_data[user_id]
        county = query.data
        if county not in ["cork", "dublin", "ambos", "toda irlanda"]:
            await query.edit_message_text("❌ Opción no válida. Por favor, elige un condado válido.")
            return
        user.county_selection = county
        
        # Si seleccionó Dublin, pedir que especifique el distrito
        if county == "dublin":
            user.state = "waiting_dublin_zone"
            keyboard = [
                [
                    InlineKeyboardButton("Dublin 1", callback_data="dublin_1"),
                    InlineKeyboardButton("Dublin 2", callback_data="dublin_2"),
                    InlineKeyboardButton("Dublin 3", callback_data="dublin_3"),
                    InlineKeyboardButton("Dublin 4", callback_data="dublin_4"),
                ],
                [
                    InlineKeyboardButton("Dublin 5", callback_data="dublin_5"),
                    InlineKeyboardButton("Dublin 6", callback_data="dublin_6"),
                    InlineKeyboardButton("Dublin 6W", callback_data="dublin_6w"),
                    InlineKeyboardButton("Dublin 7", callback_data="dublin_7"),
                ],
                [
                    InlineKeyboardButton("Dublin 8", callback_data="dublin_8"),
                    InlineKeyboardButton("Dublin 9", callback_data="dublin_9"),
                    InlineKeyboardButton("Dublin 10", callback_data="dublin_10"),
                    InlineKeyboardButton("Dublin 11", callback_data="dublin_11"),
                ],
                [
                    InlineKeyboardButton("Dublin 12", callback_data="dublin_12"),
                    InlineKeyboardButton("Dublin 13", callback_data="dublin_13"),
                    InlineKeyboardButton("Dublin 14", callback_data="dublin_14"),
                    InlineKeyboardButton("Dublin 15", callback_data="dublin_15"),
                ],
                [
                    InlineKeyboardButton("Dublin 16", callback_data="dublin_16"),
                    InlineKeyboardButton("Dublin 17", callback_data="dublin_17"),
                    InlineKeyboardButton("Dublin 18", callback_data="dublin_18"),
                    InlineKeyboardButton("Dublin 20", callback_data="dublin_20"),
                ],
                [
                    InlineKeyboardButton("Dublin 22", callback_data="dublin_22"),
                    InlineKeyboardButton("Dublin County", callback_data="dublin_23"),
                    InlineKeyboardButton("Dublin 24", callback_data="dublin_24"),
                    InlineKeyboardButton("Todo Dublin", callback_data="dublin_all")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"✅ Condado seleccionado: {county.capitalize()}\n\n"
                "Por favor, selecciona el distrito de Dublin:",
                reply_markup=reply_markup
            )
        else:
            # Si es Cork u otra opción, continuar con el flujo normal
            if getattr(user, 'presentation_mode', False):
                # Modo presentación: usar nivel por defecto y arrancar envío
                user.county_selection = county
                user.education_level = user.education_level or "primary"
                await query.edit_message_text(
                    f"✅ Condado seleccionado: {county.capitalize()}\n\n"
                    "Iniciando envío de presentación..."
                )
                await self.run_presentation_process(user_id, context)
            else:
                user.state = "waiting_education_level"
                keyboard = [
                    [InlineKeyboardButton("Pre-school", callback_data="pre-school")],
                    [InlineKeyboardButton("Primary", callback_data="primary")],
                    [InlineKeyboardButton("Post-primary", callback_data="post-primary")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    f"✅ Condado seleccionado: {county.capitalize()}\n\n"
                    "Por favor, selecciona el nivel educativo:",
                    reply_markup=reply_markup
                )

    async def handle_education_level_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Error: Por favor, inicia el proceso con /start")
            return
        user = self.user_data[user_id]
        level = query.data
        if level not in ["pre-school", "primary", "post-primary"]:
            await query.edit_message_text(
                "❌ Opción no válida. Por favor, selecciona:\n"
                "• Pre-school\n"
                "• Primary\n"
                "• Post-primary"
            )
            return
        user.education_level = level
        user.state = "scraping_in_progress"
        await query.edit_message_text(
            f"✅ Nivel educativo seleccionado: {level.capitalize()}\n\n"
            "🔍 Iniciando búsqueda de ofertas...\n"
            "Esto puede tardar unos minutos. Te mantendré informado."
        )
        await self.run_scraping_process(user_id, context)

    async def handle_dublin_zone_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Error: Por favor, inicia el proceso con /start")
            return
        user = self.user_data[user_id]
        
        zone = query.data
        if not zone.startswith("dublin_"):
            await query.edit_message_text("❌ Opción no válida. Por favor, selecciona una zona de Dublin.")
            return
        
        # Mapear la selección al distrito correspondiente
        zone_mapping = {
            "dublin_1": "Dublin 1", "dublin_2": "Dublin 2", "dublin_3": "Dublin 3",
            "dublin_4": "Dublin 4", "dublin_5": "Dublin 5", "dublin_6": "Dublin 6",
            "dublin_6w": "Dublin 6W", "dublin_7": "Dublin 7", "dublin_8": "Dublin 8",
            "dublin_9": "Dublin 9", "dublin_10": "Dublin 10", "dublin_11": "Dublin 11",
            "dublin_12": "Dublin 12", "dublin_13": "Dublin 13", "dublin_14": "Dublin 14",
            "dublin_15": "Dublin 15", "dublin_16": "Dublin 16", "dublin_17": "Dublin 17",
            "dublin_18": "Dublin 18", "dublin_20": "Dublin 20", "dublin_22": "Dublin 22",
            "dublin_23": "Dublin County", "dublin_24": "Dublin 24", "dublin_all": "Todo Dublin"
        }
        
        user.dublin_zone = zone.replace("dublin_", "")  # Almacenar sin el prefijo "dublin_"
        if getattr(user, 'presentation_mode', False):
            # Nivel por defecto para presentación
            user.education_level = user.education_level or "primary"
            await query.edit_message_text(
                f"✅ Dublin - Distrito: {zone_mapping.get(zone, 'Desconocido')}\n\n"
                "Iniciando envío de presentación..."
            )
            await self.run_presentation_process(user_id, context)
        else:
            user.state = "waiting_education_level"  # Continuar con el flujo normal
            # Mostrar opciones de nivel educativo
            keyboard = [
                [InlineKeyboardButton("Pre-school", callback_data="pre-school")],
                [InlineKeyboardButton("Primary", callback_data="primary")],
                [InlineKeyboardButton("Post-primary", callback_data="post-primary")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"✅ Condado: Dublin - Distrito: {zone_mapping.get(zone, 'Desconocido')}\n\n"
                "Por favor, selecciona el nivel educativo:",
                reply_markup=reply_markup
            )

    def _discover_presentation_pdf(self) -> Optional[str]:
        """Localiza el PDF de presentación en rutas conocidas o variable .env."""
        path = os.getenv('PRESENTATION_PDF_PATH')
        candidates = [
            path,
            os.path.join('templates', 'ProfesNomadas_Presentacion.pdf'),
            os.path.join('templates', 'profesnomadas_presentation.pdf'),
            os.path.join('assets', 'ProfesNomadas_Presentacion.pdf'),
            os.path.join('assets', 'profesnomadas_presentation.pdf'),
            # Candidatos comunes en docs/
            os.path.join('docs', 'Profes Nómadas Presentation.pdf'),
            os.path.join('docs', 'Profes Nomadas Presentation.pdf'),
            os.path.join('docs', 'profes nomadas presentation.pdf'),
            os.path.join('docs', 'profesnomadas_presentation.pdf'),
        ]
        for c in candidates:
            if c and os.path.exists(c) and c.lower().endswith('.pdf'):
                return c
        # Búsqueda flexible en docs/ si no se encontró por rutas conocidas
        try:
            docs_dir = 'docs'
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

    async def run_presentation_process(self, user_id: int, context) -> None:
        """Recoge emails de colegios y envía el PDF de presentación."""
        if self.is_scraping:
            await context.bot.send_message(chat_id=user_id, text="⚠️ Hay un proceso en curso. Intenta en unos minutos.")
            return
        self.is_scraping = True
        try:
            user = self.user_data[user_id]
            pdf_path = user.presentation_pdf or self._discover_presentation_pdf()
            if not pdf_path:
                await context.bot.send_message(chat_id=user_id, text="❌ No se encontró el PDF de presentación. Configura PRESENTATION_PDF_PATH o súbelo a templates/ o docs/.")
                return

            county_map = {"cork": "4", "dublin": "27", "toda irlanda": "", "all": ""}
            county_id = county_map.get(user.county_selection or 'all', '')
            level_map = {"pre-school": "pre_school", "primary": "primary", "post-primary": "second_level"}
            level = level_map.get(user.education_level or 'primary', 'primary')

            await context.bot.send_message(chat_id=user_id, text="🔍 Buscando colegios y correos...")

            offers: List[Dict] = []
            if (user.county_selection == 'dublin') and user.dublin_zone and user.dublin_zone != 'all':
                from src.scrapers.scraper_educationposts import DUBLIN_ZONES, DUBLIN_DISTRICTS
                districts = DUBLIN_ZONES.get(user.dublin_zone, [])
                for idx, district_id in enumerate(districts, 1):
                    scraper = EducationPosts(level=level, county_id=county_id, district_id=district_id)
                    district_offers = await scraper.fetch_all()
                    for off in district_offers:
                        off['district'] = DUBLIN_DISTRICTS.get(district_id, district_id)
                    offers.extend(district_offers)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📍 {idx}/{len(districts)} {DUBLIN_DISTRICTS.get(district_id, district_id)}: {len(district_offers)} ofertas"
                    )
                    await asyncio.sleep(2)
            else:
                scraper = EducationPosts(level=level, county_id=county_id, district_id="")
                offers = await scraper.fetch_all()

            if not offers:
                await context.bot.send_message(chat_id=user_id, text="ℹ️ No se encontraron ofertas/colegios.")
                return

            BAD_MAILS = ["noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie"]

            def _school_identifier(offer: Dict) -> str:
                roll_keys = ['roll_number', 'roll', 'rollno', 'roll_no', 'rollnumber', 'school_ref']
                for key in roll_keys:
                    val = offer.get(key)
                    if val:
                        return str(val).strip()
                name = offer.get('school') or offer.get('school_name') or ''
                return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').strip().lower()

            emails_data: List[Dict[str, str]] = []
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
                mail_lower = mail.lower()
                if mail_lower in seen_emails:
                    continue
                seen_emails.add(mail_lower)
                if school_id:
                    seen_schools.add(school_id)
                emails_data.append({
                    'email': mail,
                    'school_name': school_name,
                    'school_id': school_id,
                })

            if not emails_data:
                await context.bot.send_message(chat_id=user_id, text="ℹ️ No hay emails válidos para enviar.")
                return

            resend_api_key = os.getenv('RESEND_API_KEY')
            resend_from_email = os.getenv('RESEND_FROM_EMAIL') or user.email

            test_mode = getattr(user, 'test_mode', False)
            emails: List[Dict[str, str]] = emails_data
            skipped_count = 0

            if not test_mode:
                try:
                    already_sent = get_presentation_recipients(resend_from_email)
                except Exception as exc:
                    already_sent = set()
                    self.logger.warning(f"No se pudo consultar Firebase para presentaciones previas: {exc}")
                if already_sent:
                    filtered: List[Dict[str, str]] = []
                    for item in emails:
                        if item['email'].lower() in already_sent:
                            skipped_count += 1
                            continue
                        filtered.append(item)
                    emails = filtered
                    if skipped_count:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"ℹ️ Se omiten {skipped_count} colegios porque ya recibieron la presentación anteriormente."
                        )

            if not emails:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="ℹ️ Todos los colegios encontrados ya habían recibido la presentación anteriormente."
                )
                return

            total_to_send = len(emails)

            if test_mode:
                test_recipient = 'raulforteaibanez@gmail.com'
                emails = emails[:10]
                total_to_send = len(emails)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🧪 Modo test: enviaré {total_to_send} correos al email de test: {test_recipient}"
                )

            if not resend_api_key:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ No se pudo enviar la presentación: falta configurar RESEND_API_KEY."
                )
                return
            if not resend_from_email:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ No se pudo enviar la presentación: falta el remitente para Resend (RESEND_FROM_EMAIL)."
                )
                return

            await context.bot.send_message(chat_id=user_id, text=f"✉️ Enviando presentación a {total_to_send} colegios...")

            sender = EmailSender()

            # Inicializar Notion CRM (opcional)
            notion_crm = None
            if _NOTION_CRM_AVAILABLE:
                try:
                    notion_crm = NotionCRMManager()
                    self.logger.info("✅ Notion CRM listo para registrar contactos")
                except Exception as e:
                    self.logger.warning(f"⚠️  Notion CRM no disponible: {e}")
            # Cargar plantillas de asunto y cuerpo si existen
            subject = self._read_file_safe(os.path.join('templates', 'presentation_subject.txt')) or "Presentation – Profes Nómadas"
            body_tmpl = self._read_file_safe(os.path.join('templates', 'presentation_body.txt')) or (
                "Dear {school_name} Team,\n\n"
                "We are Profes Nómadas, a service that helps schools streamline teacher applications and communication.\n\n"
                "Please find attached a short presentation with our details.\n\n"
                "Kind regards,\nProfes Nómadas"
            )
            sent = 0
            for idx, email_info in enumerate(emails, 1):
                to_email = email_info['email']
                school_name = email_info['school_name']
                body = body_tmpl.format(school_name=school_name) if '{school_name}' in body_tmpl else body_tmpl
                if test_mode:
                    to_email = 'raulforteaibanez@gmail.com'
                ok = await sender.send_presentation_email(
                    from_email=resend_from_email,
                    from_password=None,
                    to_email=to_email,
                    presentation_pdf_path=pdf_path,
                    subject=subject,
                    body=body,
                    resend_api_key=resend_api_key,
                    resend_from_email=resend_from_email,
                )
                if ok:
                    sent += 1
                    if not test_mode:
                        try:
                            mark_presentation_sent(
                                sender_email=resend_from_email,
                                recipient_email=email_info['email'].lower(),
                                data={
                                    'school': school_name,
                                    'school_id': email_info['school_id'],
                                }
                            )
                        except Exception as exc:
                            self.logger.warning(f"No se pudo registrar en Firebase el envío de presentación a {email_info['email']}: {exc}")

                        # Registrar en Notion CRM
                        if notion_crm:
                            try:
                                # Mapear nivel educativo del scraper a las opciones de Notion
                                # level se calcula más arriba (primary / second_level / pre_school)
                                notion_level_map = {
                                    'primary': 'Primary',
                                    'second_level': 'Secondary',
                                    'pre_school': 'Pre-school',
                                }
                                # county_selection puede ser 'cork', 'dublin', 'toda irlanda'
                                county_value = (self.user_data[user_id].county_selection or '').strip().lower()
                                county_label = county_value.title() if county_value and county_value not in {'all', 'toda irlanda'} else ''

                                # dublin_zone almacenado como '1','2','6w','all', etc.
                                dz_raw = (self.user_data[user_id].dublin_zone or '').strip().lower()
                                dublin_zone_label = ''
                                if county_value == 'dublin':
                                    if dz_raw in {'all', '23'}:
                                        dublin_zone_label = 'All Dublin'
                                    elif dz_raw:
                                        if dz_raw == '6w':
                                            dublin_zone_label = 'Dublin 6W'
                                        else:
                                            dublin_zone_label = f"Dublin {dz_raw.upper()}"

                                # Nivel para Notion
                                # Reutilizamos el 'level' calculado unas líneas arriba para el scraper
                                # Si por estructura no está en alcance, derivamos de user.education_level
                                try:
                                    level_for_scraper = level
                                except NameError:
                                    ul = (self.user_data[user_id].education_level or 'primary').strip().lower()
                                    level_for_scraper = {'pre-school':'pre_school', 'post-primary':'second_level'}.get(ul, 'primary')
                                notion_level = notion_level_map.get(level_for_scraper, 'Primary')

                                notion_crm.add_school_contact(
                                    school_name=school_name,
                                    email=email_info['email'],
                                    school_id=email_info['school_id'],
                                    county=county_label,
                                    dublin_zone=dublin_zone_label,
                                    education_level=notion_level,
                                    sender_email=resend_from_email,
                                    notes='Presentación enviada automáticamente desde el bot',
                                    status='Contacted'
                                )
                            except Exception as exc:
                                self.logger.warning(f"No se pudo registrar en Notion CRM el envío a {email_info['email']}: {exc}")
                status = "✅" if ok else "❌"
                if idx % 5 == 0 or not ok:
                    await context.bot.send_message(chat_id=user_id, text=f"{status} [{idx}/{total_to_send}] {to_email}")
                await asyncio.sleep(1)

            await context.bot.send_message(chat_id=user_id, text=f"🎉 Listo. Enviados {sent}/{total_to_send} correos.")
        except Exception as e:
            self.logger.error(f"Error en presentación: {e}")
            await context.bot.send_message(chat_id=user_id, text="❌ Ocurrió un error durante el envío de la presentación.")
        finally:
            # Reset de modo presentación y estado de scraping
            try:
                self.user_data[user_id].presentation_mode = False
            except Exception:
                pass
            self.is_scraping = False

    def _read_file_safe(self, path: str) -> Optional[str]:
        try:
            if path and os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception:
            return None
        return None

    async def prepare_documents_for_offer(self, offer: Dict) -> List[str]:
        """
        Analiza los requerimientos de una oferta y devuelve la lista de documentos necesarios.
        Solo incluye los documentos que se mencionan explícitamente en la oferta.
        
        Args:
            offer: Diccionario con la información de la oferta
            
        Returns:
            Lista de documentos requeridos
        """
        required_docs = []
        description = offer.get('description', '').lower()
        requirements = offer.get('requirements', '').lower()
        
        # Mapeo simplificado de documentos requeridos
        doc_mapping = {
            # CVs
            'cv': 'CV',
            'curriculum vitae': 'CV',
            'resume': 'CV',
            
            # Certificados y diplomas
            'certificates': 'Certificates and Diplomas',
            'diplomas': 'Certificates and Diplomas',
            'degrees': 'Certificates and Diplomas',
            'qualifications': 'Certificates and Diplomas',
            
            # Formularios de solicitud en inglés
            'application form': 'Application Form',
            'standard application form': 'Application Form',
            'teaching application form': 'Application Form',
            'sna application form': 'Application Form',
            'principalship application form': 'Application Form',
            
            # Formularios de solicitud en gaélico
            'foirm iarratais': 'Application Form (Gaeilge)',
            'foirm iarratais chaighdeánach': 'Application Form (Gaeilge)',
            
            # Otros documentos
            'letter of application': 'Letter of Application',
            'teaching council': 'Teaching Council Registration',
            'teaching practice': 'Teaching Practice Grades',
            'referees': 'Referees Details',
            'referees details': 'Referees Details',  # Agregar esta variante explícita
            'reference': 'Referees Details',  # También incluir "reference"
            'references': 'Referees Details',  # También incluir "references"
            'religious education': 'Religious Education Certificate'
        }
        
        # Analizar descripción y requerimientos
        text_to_analyze = f"{description} {requirements}"
        
        # Conjunto para evitar duplicados
        found_docs = set()
        
        for key, doc in doc_mapping.items():
            if key in text_to_analyze and doc not in found_docs:
                required_docs.append(doc)
                found_docs.add(doc)
            
        return required_docs

    async def generate_application_form(self, offer: Dict, user: UserData) -> str:
        """
        Genera un PDF personalizado del Application Form usando la plantilla que subió el usuario por Telegram.
        
        Args:
            offer: Diccionario con la información de la oferta
            user: Datos del usuario
            
        Returns:
            str: Ruta al archivo PDF generado
        """
        try:
            # Verificar que el usuario tiene un Application Form subido
            if not user.documents.get('application_form'):
                self.logger.error("No se encontró Application Form subido por el usuario")
                return None
            
            # Obtener la ruta del PDF plantilla
            template_path = user.documents['application_form']['path'] if isinstance(user.documents['application_form'], dict) else user.documents['application_form']
            
            if not template_path or not os.path.exists(template_path):
                self.logger.error(f"Application Form no encontrado en: {template_path}")
                return None
            
            # Preparar datos de la oferta para la personalización
            from src.scrapers.scraper_educationposts import EducationPosts
            scraper = EducationPosts()
            offer_data = scraper.prepare_offer_data_for_application_form(offer)
            
            # Crear directorio temporal si no existe
            os.makedirs("temp", exist_ok=True)
            
            # Generar nombre único para el archivo personalizado
            school_name = offer.get('school_name', offer.get('school', 'Unknown')).replace(' ', '_').lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"application_form_{school_name}_{timestamp}.pdf"
            output_path = os.path.join("temp", filename)
            
            # Personalizar el PDF usando la plantilla del usuario
            document_reader = DocumentReader()
            customized_path = document_reader.customize_application_form_pdf(
                template_path=template_path,
                output_path=output_path,
                offer_data=offer_data
            )
            
            if customized_path and os.path.exists(customized_path):
                self.logger.info(f"Application Form personalizado generado: {customized_path}")
                return customized_path
            else:
                self.logger.error("Error al personalizar Application Form")
                return None
            
        except Exception as e:
            self.logger.error(f"Error generando Application Form personalizado: {str(e)}")
            return None

    def _get_tc_info(self, user: UserData, attachments: List[str]) -> str:
        """Genera el texto informativo sobre el Teaching Council basado en los datos del usuario."""
        if not user.teaching_council_registration:
            return ""

        # Por defecto, se asume que se posee el TC si no se especifica un documento
        tc_info = ""
        tc_registration_is_image = False

        # Verificar si el documento de TC es una imagen
        for doc_path in attachments:
            if any(keyword in os.path.basename(doc_path).lower() for keyword in ['tc', 'registration', 'teaching council']):
                ext = os.path.splitext(doc_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.bmp', '.tiff', '.gif']:
                    tc_registration_is_image = True
                    break
        
        # Si el documento es una imagen, se considera "en proceso"
        if tc_registration_is_image:
            if user.tc_route:
                tc_info = f" My application for the Teaching Council number {user.tc_route} has already been submitted and is currently being processed."
            else:
                tc_info = " My application for the Teaching Council has already been submitted and is currently being processed."
        # Si no es una imagen (es un PDF o no hay documento pero marcó 'sí')
        else:
            if user.tc_route:
                tc_info = f" I already possess the Teaching Council Number route {user.tc_route}."
            else:
                tc_info = " I already possess the Teaching Council Number."
        
        return tc_info

    async def send_application_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Envía un correo electrónico de solicitud para una oferta específica.
        """
        if not await self.is_authorized(update):
            return
            
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            await update.message.reply_text("❌ No se encontró tu información. Por favor, inicia el bot con /start")
            return
            
        user = self.user_data[user_id]
        
        # Verificar que se hayan completado los datos básicos del formulario
        if not user.has_required_form_data():
            await update.message.reply_text(
                "❌ Faltan datos básicos requeridos (nombre y correo electrónico).\n" +
                "Por favor, inicia el bot nuevamente con /start y completa estos datos."
            )
            return
        
        # Comprobación de documentos obligatorios antes de aplicar
        app_form_ok = False
        app_form_path = None
        for key in user.documents:
            if key == 'application_form':
                doc_info = user.documents[key]
                if doc_info:
                    path = doc_info['path'] if isinstance(doc_info, dict) else doc_info
                    if path and (path.endswith('.pdf')):
                        app_form_ok = True
                        app_form_path = path
                        break
        if not app_form_ok:
            await update.message.reply_text(
                "❌ Falta el Application Form.\n\n"
                "Por favor, descarga la plantilla, rellénala y súbela aquí en formato .pdf antes de aplicar.\n\n"
                "📝 IMPORTANTE: Para que el sistema personalice automáticamente tu Application Form con los datos de la oferta "
                "(POSITION ADVERTISED, School y ROLL NUMBER), asegúrate de subirlo en formato .pdf."
            )
            return
        
        # Verificar que se hayan enviado todos los documentos obligatorios según la oferta
        offer_required_docs = offer.get('required_documents', [])
        # Mapeo flexible de nombres de documentos requeridos a claves internas
        doc_synonyms = {
            'applicationform': None,
            'application form': None,
            'standard application form': None,
            'applicationformenglish': None,
            'application form (english)': None,
            'applicationform(english)': None,
            'standardapplicationform': None,
            'standard application form (english)': None,
            'standardapplicationform(english)': None,
            'cv': 'cv',
            'curriculumvitae': 'cv',
            'resume': 'cv',
            'letterofapplication': 'letter_of_application',
            'letter of application': 'letter_of_application',
            'certificatesanddiplomas': 'degree',
            'certificates and diplomas': 'degree',
            'degrees': 'degree',
            'qualifications': 'degree',
            'degree': 'degree',
            'teachingcouncilregistration': 'tc_registration',
            'teaching council registration': 'tc_registration',
            'religiouseducationcertificate': 'religion_certificate',
            'religious education certificate': 'religion_certificate',
            'teachingpracticegrades': 'teaching_practice',
            'teaching practice grades': 'teaching_practice',
            'teaching practice': 'teaching_practice',
            'refereesdetails': 'referees',
            'referees details': 'referees',
            'referees': 'referees',
            'references': 'referees',
            'references': 'referentes',
        }
        def normalize(doc):
            return doc.lower().replace(' ', '').replace('-', '').replace('_', '')
        
        missing_docs = []
        for req in offer_required_docs:
            norm = normalize(req)
            if norm in doc_synonyms:
                key = doc_synonyms[norm]
                if key is None:
                    # Para application form, verificar si necesitamos generarlo
                    # (Este bloque se ha simplificado para evitar errores)
                    logger.info(f"Se requiere application form para la oferta")
                    continue
                
                if not user.documents.get(key):
                    missing_docs.append(req)
            else:
                # Si no está en el mapeo, buscar coincidencia directa en user.documents
                if not user.documents.get(norm):
                    missing_docs.append(req)
                    
        if missing_docs:
            await update.message.reply_text(
                "❌ Faltan documentos obligatorios:\n" +
                "\n".join(f"• {doc}" for doc in missing_docs) +
                "\n\nPor favor, envía todos los documentos requeridos antes de enviar la aplicación."
            )
            return
            
        # Verificar que se haya seleccionado una oferta
        if not context.user_data.get('selected_offer'):
            await update.message.reply_text("❌ No se ha seleccionado ninguna oferta. Por favor, selecciona una oferta primero.")
            return
            
        offer = context.user_data['selected_offer']
        
        # Preparar datos para personalizar documentos
        # Preparar datos de oferta para personalización
        from src.scrapers.scraper_educationposts import EducationPosts
        scraper = EducationPosts()
        offer_data = scraper.prepare_offer_data_for_application_form(offer)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        school_name = offer['school_name'].replace(' ', '_').lower()
        document_reader = DocumentReader()
        
        # Personalizar documentos (Application Form en PDF, Teaching Practice y Referees en DOCX)
        processed_docs = []
        customized_paths = {}
        
        # Comprobar cada documento obligatorio (excepto Letter of Application que nunca se personaliza)
        for doc_type, doc_path in [
            ('application_form', app_form_path),  # Ya verificamos que existe
            ('teaching_practice', user.documents.get('teaching_practice')),
            ('referees', user.documents.get('referees'))
        ]:
            # Verificar si existe y es del formato correcto
            if doc_path and isinstance(doc_path, str):
                if doc_type == 'application_form' and doc_path.endswith('.pdf'):
                    # Personalizar Application Form PDF
                    doc_type_name = "Application Form"
                    processing_msg = await update.message.reply_text(f"⏳ Personalizando {doc_type_name} con los datos de la oferta...")
                    
                    # Nombre único para el archivo personalizado
                    custom_filename = f"{doc_type}_{school_name}_{timestamp}.pdf"
                    custom_filepath = os.path.join('temp', custom_filename)
                    
                    # Personalizar el documento PDF
                    customized_path = document_reader.customize_application_form_pdf(
                        template_path=doc_path,
                        output_path=custom_filepath,
                        offer_data=offer_data
                    )
                    
                    if customized_path:
                        logger.info(f"{doc_type_name} personalizado correctamente: {customized_path}")
                        await processing_msg.edit_text(
                            f"✅ {doc_type_name} personalizado correctamente con los datos de la oferta:\n\n"
                            f"📌 Posición: {offer_data['position']}\n"
                            f"📌 Escuela: {offer.get('school_name', offer.get('school', 'Unknown'))}\n"
                            f"📌 Roll Number: {offer_data['roll_number']}"
                        )
                        customized_paths[doc_type] = customized_path
                        processed_docs.append(doc_type_name)
                    else:
                        logger.error(f"Error al personalizar {doc_type_name}")
                        await processing_msg.edit_text(f"⚠️ No se pudo personalizar el {doc_type_name}, se utilizará el original.")
                
                elif doc_type in ['teaching_practice', 'referees'] and doc_path.endswith('.docx'):
                    # Personalizar documentos DOCX (Teaching Practice y Referees)
                    doc_type_name = "Teaching Practice" if doc_type == 'teaching_practice' else "Referees Details"
                    processing_msg = await update.message.reply_text(f"⏳ Personalizando {doc_type_name} con los datos de la oferta...")
                    
                    # Nombre único para el archivo personalizado
                    custom_filename = f"{doc_type}_{school_name}_{timestamp}.docx"
                    custom_filepath = os.path.join('temp', custom_filename)
                    
                    # Personalizar el documento DOCX
                    customized_path = document_reader.customize_application_form(
                        template_path=doc_path,
                        output_path=custom_filepath,
                        offer_data=offer_data
                    )
                    
                    if customized_path:
                        logger.info(f"{doc_type_name} personalizado correctamente: {customized_path}")
                        await processing_msg.edit_text(
                            f"✅ {doc_type_name} personalizado correctamente con los datos de la oferta:\n\n"
                            f"📌 Posición: {offer_data['position']}\n"
                            f"📌 Escuela: {offer.get('school_name', offer.get('school', 'Unknown'))}\n"
                            f"📌 Roll Number: {offer_data['roll_number']}"
                        )
                        customized_paths[doc_type] = customized_path
                        processed_docs.append(doc_type_name)
                    else:
                        logger.error(f"Error al personalizar {doc_type_name}")
                        await processing_msg.edit_text(f"⚠️ No se pudo personalizar el {doc_type_name}, se utilizará el original.")
        
        # Si se personalizaron documentos, mostrar resumen
        if processed_docs:
            await update.message.reply_text(
                f"📝 Se han personalizado {len(processed_docs)} documentos con éxito:\n"
                + "\n".join(f"• {doc}" for doc in processed_docs)
            )
        
        # Generar el formulario de aplicación (PDF)
        form_path = await self.generate_application_form(offer, user)
        
        if not form_path:
            await update.message.reply_text("❌ Error al generar el formulario de aplicación.")
            return
            
        # Preparar los adjuntos basándose en los documentos requeridos por la oferta
        attachments = []
        
        # Preparar customized_paths con el Application Form
        customized_paths = {'application_form': form_path}
        
        # Obtener documentos requeridos y adjuntarlos
        required_attachments = self.get_required_attachments(offer, user, customized_paths)
        attachments.extend(required_attachments)
        
        # Log de documentos adjuntados
        self.logger.info(f"Documentos adjuntados para {offer.get('school_name', offer.get('school', 'School'))}:")
        for doc_path in required_attachments:
            self.logger.info(f"- {os.path.basename(doc_path)}")
        
        # Preparar el cuerpo del email
        # Determinar el nivel educativo para el email
        education_level = user.education_level or "Primary Education"
        if education_level == "pre-school":
            education_level = "Pre-school Education"
        elif education_level == "primary":
            education_level = "Primary Education"
        elif education_level == "post-primary":
            education_level = "Post-primary Education"
        
        # Determinar si tiene Teaching Council Number
        tc_info = self._get_tc_info(user, attachments)
        
        # Construir cuerpo del email
        email_body = f"""Dear Sir or Madam,

I am {user.name}, a {education_level} Teacher.{tc_info}

I found your school and I believe my teaching style is highly aligned with your requirements and values. I am truly interested in working with you as a {education_level} Teacher.

Here I attach all the required documents for the application. If you need any further information, please do not hesitate to contact me.

Hope to hear from you soon,

{user.name}
{user.email}"""
        
        # Enviar el email
        try:
            await self.email_sender.send_email(
                to_email=offer['email'],
                subject=f"Teaching post application for {offer['position']} - {user.name}",
                body=email_body,
                attachments=attachments,
                user_email=user.email,
                user_password=user.email_password
            )
            
            # Registrar la aplicación en Firebase
            await self.firebase_service.register_application(
                user_email=user.email,
                offer_url=offer['url']
            )
            
            await update.message.reply_text(
                "✅ Email enviado correctamente.\n\n"
                "Se ha registrado tu aplicación en la base de datos."
            )
            
        except Exception as e:
            logger.error(f"Error al enviar email: {str(e)}")
            await update.message.reply_text(
                "❌ Error al enviar el email. Por favor, verifica tu email y contraseña de aplicación."
            )
       

    async def send_test_email(self, offer: Dict, from_email: str, from_password: str) -> bool:
        """
        Envía un email de prueba a raulforteabusiness@gmail.com con los detalles de la oferta.
        """
        try:
            # Comprobar requerimientos/documentos
            required_docs = offer.get('required_documents', [])
            requirements = offer.get('requirements', '').strip()
            if not required_docs or all(not doc.strip() for doc in required_docs) or requirements.lower() in ('', 'textaparent', 'n/a', 'no requirements'):
                self.logger.warning("No se detectaron requerimientos/documentos válidos. No se enviará email de prueba.")
                return False

            # Crear mensaje formal y personalizado
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = "raulforteabusiness@gmail.com"
            msg['Subject'] = f"[TEST] Teaching post application for {offer.get('position', offer.get('vacancy', 'Teaching Position'))} at {offer.get('school', offer.get('school_name', 'School'))}"

            doc_lines = '\n'.join(['- ' + doc for doc in required_docs])
            # Buscar el usuario correspondiente al email de origen
            user = None
            for u in self.user_data.values():
                if u.email and u.email.strip().lower() == from_email.strip().lower():
                    user = u
                    break
            if not user:
                self.logger.error("No se encontró el usuario correspondiente al email de origen. No se puede adjuntar documentos ni enviar el correo.")
                return False
            
            # Generar el formulario de aplicación personalizado
            form_path = await self.generate_application_form(offer, user)
            if not form_path or not os.path.exists(form_path):
                self.logger.error("No se pudo generar el formulario de aplicación. No se enviará el email.")
                return False
            
            # Obtener documentos requeridos usando la misma función que el método principal
            customized_paths = {'application_form': form_path}
            required_attachments = self.get_required_attachments(offer, user, customized_paths)
            
            # Preparar adjuntos: solo incluir los documentos requeridos
            attachments = required_attachments
            
            # Log de documentos adjuntados
            self.logger.info(f"Documentos adjuntados para email de prueba de {offer.get('school_name', 'School')}:")
            for doc_path in required_attachments:
                self.logger.info(f"- {os.path.basename(doc_path)}")
            
            # Aquí ya es seguro acceder a user.name, user.email, user.documents, etc.
            # Determinar el nivel educativo para el email
            education_level = user.education_level or "Primary Education"
            if education_level == "pre-school":
                education_level = "Pre-school Education"
            elif education_level == "primary":
                education_level = "Primary Education"
            elif education_level == "post-primary":
                education_level = "Post-primary Education"
            
            # Determinar si tiene Teaching Council Number
            tc_info = self._get_tc_info(user, attachments)
            
            body = f"""Dear Sir or Madam,

I am {user.name}, a {education_level} Teacher.{tc_info}

I found your school and I believe my teaching style is highly aligned with your requirements and values. I am truly interested in working with you as a {education_level} Teacher.

Here I attach all the required documents for the application. If you need any further information, please do not hesitate to contact me.

Hope to hear from you soon,

{user.name}
{user.email}"""
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Adjuntar todos los documentos
            for doc_path in attachments:
                if os.path.exists(doc_path):
                    with open(doc_path, 'rb') as f:
                        part = MIMEBase('application', 'pdf')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = os.path.basename(doc_path)
                        part.add_header('Content-Disposition', f'attachment; filename={filename}')
                        msg.attach(part)
                        self.logger.info(f"Adjuntado: {filename}")
                else:
                    self.logger.warning(f"Archivo no encontrado: {doc_path}")

            # Conectar al servidor SMTP de Gmail
            self.logger.info(f"Conectando a SMTP: smtp.gmail.com:587")
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            self.logger.info("Authenticating the SMTP test send.")
            server.login(from_email, from_password)
            self.logger.info("Sending SMTP test email.")
            server.send_message(msg)
            server.quit()
            self.logger.info("Email enviado correctamente")
            return True
        except Exception as e:
            self.logger.error("SMTP test email failed (%s).", type(e).__name__)
            return False

    @staticmethod
    def _send_application_smtp_message(msg, from_email, from_password, to_email):
        """Perform SMTP I/O outside the Telegram event loop."""
        try:
            smtp_context = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls(context=smtp_context)
                server.login(from_email, from_password)
                server.sendmail(from_email, to_email, msg.as_string())
            return True, None, False
        except smtplib.SMTPAuthenticationError:
            return False, "smtp_authentication_failed", True
        except smtplib.SMTPRecipientsRefused:
            return False, "smtp_recipient_rejected", True
        except (smtplib.SMTPException, OSError):
            # Delivery may be indeterminate after DATA; preserve the reservation.
            return False, "smtp_delivery_indeterminate", False
        except Exception:
            return False, "smtp_unexpected_error", False

    async def send_application_email_for_offer(
        self,
        offer: Dict,
        from_email: str,
        from_password: str,
        run_id: Optional[str] = None,
    ) -> bool:
        """Send one application email after reserving a privacy-safe delivery slot."""
        run_id = run_id or uuid.uuid4().hex
        decision = None
        reservation_settled = False
        form_path = None
        customized_paths = {}
        self._last_application_send_reason = None

        # Offers with a web application route must never be emailed by the bot.
        if offer.get('apply_link'):
            user = next(
                (
                    candidate
                    for candidate in self.user_data.values()
                    if candidate.email
                    and candidate.email.strip().lower() == from_email.strip().lower()
                ),
                None,
            )
            if user and getattr(user, 'chat_id', None):
                asyncio.create_task(
                    self.application.bot.send_message(
                        chat_id=user.chat_id,
                        text=(
                            "ℹ️ Esta oferta requiere que apliques manualmente a través de la web. "
                            "No es posible enviar la aplicación por email.\n\n"
                            f"Por favor, haz clic en el siguiente enlace y sigue las instrucciones para aplicar: \n{offer['url']}"
                        ),
                    )
                )
            await self.send_policy.audit.emit_async(
                "application_send_skipped",
                run_id=run_id,
                outcome="skipped",
                decision="external_application_route",
            )
            self._last_application_send_reason = "external_application_route"
            return False

        try:
            user = next(
                (
                    candidate
                    for candidate in self.user_data.values()
                    if candidate.email
                    and candidate.email.strip().lower() == from_email.strip().lower()
                ),
                None,
            )
            if not user:
                self.logger.warning("Application email skipped: sender account was not found.")
                self._last_application_send_reason = "sender_not_found"
                return False

            to_email = offer.get("email")
            if not to_email:
                self.logger.warning("Application email skipped: offer has no recipient.")
                self._last_application_send_reason = "recipient_missing"
                return False

            test_mode = bool(getattr(user, "test_mode", False))
            if test_mode:
                to_email = "raulforteabusiness@gmail.com"

            decision = await self.send_policy.reserve_async(
                account_email=user.email,
                recipient_email=to_email,
                offer=offer,
                run_id=run_id,
                test_mode=test_mode,
            )
            self._last_application_send_reason = decision.reason
            if not decision.allowed:
                self.logger.warning("Application email skipped by send policy: %s", decision.reason)
                return False

            # The persisted reservation allocates a turn, including across processes.
            if decision.delay_seconds:
                await asyncio.sleep(decision.delay_seconds)

            form_path = await self.generate_application_form(offer, user)
            if not form_path or not os.path.exists(form_path):
                self.logger.error("Application email skipped: application form could not be generated.")
                await self.send_policy.release_after_definite_failure_async(
                    decision, run_id, "preflight_failed"
                )
                reservation_settled = True
                self._last_application_send_reason = "preflight_failed"
                return False

            customized_paths = {"application_form": form_path}
            attachments = self.get_required_attachments(offer, user, customized_paths)
            education_level = user.education_level or "Primary Education"
            if education_level == "pre-school":
                education_level = "Pre-school Education"
            elif education_level == "primary":
                education_level = "Primary Education"
            elif education_level == "post-primary":
                education_level = "Post-primary Education"

            tc_info = self._get_tc_info(user, attachments)
            body = f"""Dear Sir or Madam,

I am {user.name}, a {education_level} Teacher.{tc_info}

I found your school and I believe my teaching style is highly aligned with your requirements and values. I am truly interested in working with you as a {education_level} Teacher.

Here I attach all the required documents for the application. If you need any further information, please do not hesitate to contact me.

Hope to hear from you soon,

{user.name}
{user.email}"""
            subject = (
                "[TEST] " if test_mode else ""
            ) + (
                f"Teaching post application for "
                f"{offer.get('position', offer.get('vacancy', 'Teaching Position'))} "
                f"at {offer.get('school', offer.get('school_name', 'School'))}"
            )

            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            for doc_path in attachments:
                if not os.path.exists(doc_path):
                    continue
                doc_type = None
                original_filename = os.path.basename(doc_path)
                for key, doc_info in user.documents.items():
                    if doc_info and doc_info.get("path") == doc_path:
                        doc_type = key
                        original_filename = doc_info.get("filename", original_filename)
                        break

                final_filename = original_filename
                if doc_type == "degree":
                    final_filename = "Degree.pdf"
                elif doc_type == "tc_registration":
                    extension = os.path.splitext(original_filename)[1] or ".pdf"
                    final_filename = f"TC_Registration{extension}"
                elif "application_form_" in doc_path:
                    final_filename = "Application Form.pdf"

                with open(doc_path, "rb") as document:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(document.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f'attachment; filename="{final_filename}"'
                )
                msg.attach(part)

            loop = asyncio.get_running_loop()
            success, error_category, definite_failure = await loop.run_in_executor(
                None,
                functools.partial(
                    self._send_application_smtp_message,
                    msg,
                    from_email,
                    from_password,
                    to_email,
                ),
            )

            await self.send_policy.record_smtp_result_async(
                decision,
                run_id,
                success=success,
                error_category=error_category,
            )
            if success:
                await self.send_policy.mark_sent_async(decision, run_id)
                reservation_settled = True
                self.logger.info("Application email accepted by SMTP.")
            elif definite_failure:
                await self.send_policy.release_after_definite_failure_async(
                    decision, run_id, error_category
                )
                reservation_settled = True
                self.logger.warning("Application email was definitively rejected (%s).", error_category)
            else:
                self.logger.warning(
                    "Application email result is indeterminate; reservation remains locked for review (%s).",
                    error_category,
                )

            if success and not test_mode:
                offer_id = (
                    offer.get("id")
                    or offer.get("vacancy_id")
                    or offer.get("url", "").split("/")[-1]
                    or "unknown"
                )
                await loop.run_in_executor(
                    None,
                    functools.partial(
                        mark_vacancy_as_applied,
                        user.email,
                        offer_id,
                        data={
                            "school": offer.get("school", ""),
                            "vacancy": offer.get("vacancy", ""),
                            "email": offer.get("email", ""),
                            "applied_at": datetime.now().isoformat(),
                        },
                    ),
                )
            self._last_application_send_reason = "sent" if success else error_category
            return success
        except Exception:
            self.logger.error("Application email failed before SMTP completion.")
            if decision and not reservation_settled:
                await self.send_policy.release_after_definite_failure_async(
                    decision, run_id, "preflight_unexpected_error"
                )
            self._last_application_send_reason = "preflight_unexpected_error"
            return False
        finally:
            files_to_delete = set([form_path] + list(customized_paths.values()))
            for file_path in files_to_delete:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except OSError:
                    pass

    async def simulate_application(self, offers: List[Dict], user_id: int, context, from_email: str, from_password: str) -> None:
        """Persist and drain the automatic delivery queue from this live session."""
        if not offers:
            await context.bot.send_message(chat_id=user_id, text="❌ No hay ofertas para enviar emails.")
            return
        bad_mails = ["noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie"]
        mail_offers = [
            offer
            for offer in offers
            if offer.get("email")
            and not any(marker in offer["email"].lower() for marker in bad_mails)
        ]
        if not mail_offers:
            await context.bot.send_message(
                chat_id=user_id, text="❌ No hay ofertas con email válido para enviar emails."
            )
            return

        user = self.user_data[user_id]
        run_id = uuid.uuid4().hex
        manual_offers = [offer for offer in mail_offers if offer.get("apply_link")]
        valid_offers = [offer for offer in mail_offers if not offer.get("apply_link")]
        for offer in manual_offers:
            await self.send_application_email_for_offer(
                offer, from_email, from_password, run_id=run_id
            )
        if not valid_offers:
            return
        test_mode = bool(getattr(user, "test_mode", False))
        queue = ApplicationDeliveryQueue(
            policy=self.send_policy,
            account_email=user.email,
            run_id=run_id,
            test_mode=test_mode,
        )
        queue_items, enqueue_skipped_count = await queue.enqueue(valid_offers)
        await self.send_policy.audit.emit_async(
            "application_send_run_started",
            run_id=run_id,
            account_id=self.send_policy.audit.account_id(user.email),
            requested_offer_count=len(offers),
            eligible_offer_count=len(valid_offers),
            queued_count=len(queue_items),
            batch_offer_count=min(len(queue_items), self.send_policy.batch_limit),
            batch_limit=self.send_policy.batch_limit,
            daily_limit=self.send_policy.daily_limit,
            test_mode=test_mode,
        )
        if not queue_items:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ No se añadieron ofertas nuevas a la cola; se conservaron los bloqueos de deduplicación.",
            )
            return

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📬 Cola {'de TEST local' if test_mode else 'persistente'} iniciada: "
                f"{len(queue_items)} ofertas. Se enviarán lotes de "
                f"{self.send_policy.batch_limit} cada {self.send_policy.batch_pause_seconds} segundos, "
                f"con {self.send_policy.min_interval_seconds} segundos entre envíos."
            ),
        )
        progress_index = 0

        async def send_queued_offer(offer: Dict) -> DeliveryAttempt:
            nonlocal progress_index
            progress_index += 1
            sim_msg = (
                f"[{progress_index}/{len(queue_items)}] Enviando email "
                f"{'de TEST' if test_mode else 'real'} para: "
                f"{offer.get('school', 'N/A')} - {offer.get('vacancy', 'N/A')}\n"
            )
            await context.bot.send_message(chat_id=user_id, text=sim_msg)
            success = await self.send_application_email_for_offer(
                offer, from_email, from_password, run_id=run_id
            )
            reason = self._last_application_send_reason or "unknown"
            if success:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ [{progress_index}/{len(queue_items)}] Email enviado correctamente.",
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⚠️ [{progress_index}/{len(queue_items)}] No se envió el email "
                        f"({reason})."
                    ),
                )
            return DeliveryAttempt(
                success=success,
                reason=reason,
                error_category=None if success else reason,
            )

        async def announce_batch_pause(batch_number: int) -> None:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"⏸️ Lote {batch_number} terminado. Esperando "
                    f"{self.send_policy.batch_pause_seconds} segundos antes del siguiente lote."
                ),
            )

        result = await queue.drain(
            queue_items,
            send_queued_offer,
            on_batch_pause=announce_batch_pause,
        )

        await self.send_policy.audit.emit_async(
            "application_send_run_completed",
            run_id=run_id,
            account_id=self.send_policy.audit.account_id(user.email),
            sent_count=result.sent_count,
            skipped_count=result.skipped_count + enqueue_skipped_count,
            queued_count=result.queued_count,
            batch_offer_count=min(result.queued_count, self.send_policy.batch_limit),
            daily_limit=self.send_policy.daily_limit,
            decision=result.stopped_reason,
            outcome="daily_limit_reached" if result.deferred_daily_limit else "completed",
        )
        completion_text = (
            f"🎉 Cola finalizada para esta sesión. Emails enviados: "
            f"{result.sent_count}/{result.queued_count}. Omitidos por seguridad: "
            f"{result.skipped_count + enqueue_skipped_count}."
        )
        if result.deferred_daily_limit:
            completion_text += " Se alcanzó el máximo diario; el resto permanece en cola."
        elif result.stopped_reason == "smtp_authentication_failed":
            completion_text += " La autenticación SMTP falló; las ofertas pendientes siguen en cola."
        await context.bot.send_message(
            chat_id=user_id,
            text=completion_text,
        )
        self.clean_temp_folder()

    async def run_scraping_process(self, user_id: int, context) -> None:
        if self.is_scraping:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Ya hay un proceso de scraping en curso. Por favor, espera a que termine."
            )
            return
        self.is_scraping = True
        user = self.user_data[user_id]
        county_map = {"cork": "4", "dublin": "27"}
        level_map = {"pre-school": "pre_school", "primary": "primary", "post-primary": "second_level"}
        county_id = county_map.get(user.county_selection, "")
        level = level_map.get(user.education_level, "primary")
        
        # Mensaje inicial con información de zona si es Dublin
        location_info = ""
        if user.county_selection == "dublin" and user.dublin_zone:
            zone_display_names = {
                "1": "Dublin 1", "2": "Dublin 2", "3": "Dublin 3", "4": "Dublin 4",
                "5": "Dublin 5", "6": "Dublin 6", "6w": "Dublin 6W", "7": "Dublin 7",
                "8": "Dublin 8", "9": "Dublin 9", "10": "Dublin 10", "11": "Dublin 11",
                "12": "Dublin 12", "13": "Dublin 13", "14": "Dublin 14", "15": "Dublin 15",
                "16": "Dublin 16", "17": "Dublin 17", "18": "Dublin 18", "20": "Dublin 20",
                "22": "Dublin 22", "23": "Dublin County", "24": "Dublin 24", "all": "Todo Dublin"
            }
            location_info = f" ({zone_display_names.get(user.dublin_zone, 'Todo Dublin')})"
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🚀 Iniciando scraping para {user.county_selection.capitalize()}{location_info} - {user.education_level.capitalize()}..."
            )
            
            # Si es Dublin y se ha seleccionado una zona específica
            from src.scrapers.scraper_educationposts import DUBLIN_ZONES, DUBLIN_DISTRICTS
            
            offers = []
            excluded_etb_count = 0
            excluded_etb_names = []

            def collect_excluded_etb_listings(scraper):
                """Collect the scraper's ETB exclusions without exposing emails."""
                nonlocal excluded_etb_count
                excluded_etb_count += getattr(scraper, "excluded_school_counts", {}).get("ETB", 0)
                for school_name in getattr(scraper, "excluded_school_names_by_reason", {}).get("ETB", []):
                    if school_name not in excluded_etb_names:
                        excluded_etb_names.append(school_name)

            if user.county_selection == "dublin" and user.dublin_zone and user.dublin_zone != "all":
                # Para zonas específicas de Dublin, hacer scraping en todos los distritos de esa zona
                districts = DUBLIN_ZONES.get(user.dublin_zone, [])
                
                if districts:
                    total_districts = len(districts)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🔍 Buscando en el distrito {zone_display_names.get(user.dublin_zone, 'desconocido')} de Dublin..."
                    )
                    
                    all_offers = []
                    for idx, district_id in enumerate(districts, 1):
                        district_name = DUBLIN_DISTRICTS.get(district_id, f"Dublin Distrito {district_id}")
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"📍 {idx}/{total_districts}: Buscando en {district_name}..."
                        )
                        
                        # Crear scraper para este distrito específico
                        scraper = EducationPosts(level=level, county_id=county_id, district_id=district_id)
                        district_offers = await scraper.fetch_all()  # Limitamos a 5 por distrito para evitar sobrecarga
                        collect_excluded_etb_listings(scraper)
                        
                        if district_offers:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"✅ {district_name}: Encontradas {len(district_offers)} ofertas"
                            )
                            # Añadir información del distrito a cada oferta
                            for offer in district_offers:
                                offer['district'] = district_name
                            
                            all_offers.extend(district_offers)
                        else:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"ℹ️ {district_name}: No se encontraron ofertas"
                            )
                        
                        # Pausa entre distritos para evitar sobrecarga
                        await asyncio.sleep(3)
                    
                    offers = all_offers
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ Búsqueda completada: Encontradas {len(offers)} ofertas en {total_districts} distritos"
                    )
                else:
                    # Si no hay distritos definidos para la zona, usar todo Dublin
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"ℹ️ El distrito seleccionado ({zone_display_names.get(user.dublin_zone, user.dublin_zone)}) no está disponible. Buscando en todo Dublin..."
                    )
                    scraper = EducationPosts(level=level, county_id=county_id, district_id="")
                    offers = await scraper.fetch_all()
                    collect_excluded_etb_listings(scraper)
            else:
                # Para Cork o todo Dublin, usar el scraper normal
                scraper = EducationPosts(level=level, county_id=county_id, district_id="")
                offers = await scraper.fetch_all()
                collect_excluded_etb_listings(scraper)

            if excluded_etb_count:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=format_etb_exclusion_notice(
                            excluded_etb_count, excluded_etb_names
                        ),
                    )
                except Exception as exc:
                    # A notification failure must not turn a successful scrape
                    # into an aborted run.
                    logger.warning(
                        "Could not send ETB exclusion notice (%s)", type(exc).__name__
                    )
                
            if not offers:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ No se encontraron ofertas educativas."
                )
                return
            # --- INTEGRACIÓN FIREBASE: filtrar ofertas ya aplicadas ---
            applied_ids = get_applied_vacancies(user.email)
            offers = [o for o in offers if self.get_offer_id(o) not in applied_ids]
            if not offers:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✅ Ya has aplicado a todas las vacantes nuevas."
                )
                return
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📋 Analizando {len(offers)} ofertas encontradas (no repetidas)..."
            )
            for offer in offers:
                offer['required_documents'] = await self.prepare_documents_for_offer(offer)
            # Proceso de simulación/aplicación múltiple
            for offer in offers:
                # Comprobar si el usuario tiene todos los datos y documentos requeridos para esta oferta
                missing = []
                # Comprobar datos del formulario
                if not user.has_required_form_data():
                    missing.append('datos del formulario')
                # Comprobar documentos requeridos
                offer_required_docs = offer.get('required_documents', [])
                doc_synonyms = {
                    'applicationform': None,
                    'application form': None,
                    'standard application form': None,
                    'applicationformenglish': None,
                    'application form (english)': None,
                    'applicationform(english)': None,
                    'standardapplicationform': None,
                    'standard application form (english)': None,
                    'standardapplicationform(english)': None,
                    'cv': 'cv',
                    'curriculumvitae': 'cv',
                    'resume': 'cv',
                    'letterofapplication': 'letter_of_application',
                    'letter of application': 'letter_of_application',
                    'certificatesanddiplomas': 'degree',
                    'certificates and diplomas': 'degree',
                    'degrees': 'degree',
                    'qualifications': 'degree',
                    'degree': 'degree',
                    'teachingcouncilregistration': 'tc_registration',
                    'teaching council registration': 'tc_registration',
                    'religiouseducationcertificate': 'religion_certificate',
                    'religious education certificate': 'religion_certificate',
                    'teachingpracticegrades': 'teaching_practice',
                    'teaching practice grades': 'teaching_practice',
                    'teaching practice': 'teaching_practice',
                    'refereesdetails': 'referees',
                    'referees details': 'referees',
                    'referees': 'referees',
                    'references': 'referees',
                }
                def normalize(doc):
                    return doc.lower().replace(' ', '').replace('-', '').replace('_', '')
                logger.info(f"Verificando documentos requeridos para esta oferta: {offer_required_docs}")
                logger.info(f"Documentos disponibles del usuario: {list(user.documents.keys())}")
                
                for req in offer_required_docs:
                    norm = normalize(req)
                    logger.info(f"Verificando documento requerido: {req} (normalizado: {norm})")
                    
                    if norm in doc_synonyms:
                        key = doc_synonyms[norm]
                        logger.info(f"  • Mapeado a clave interna: {key}")
                        
                        if key is None:
                            logger.info(f"  • Documento ignorado (application form ya incluido en verificación anterior)")
                            continue
                            
                        if not user.documents.get(key):
                            missing.append(req)
                            logger.info(f"  • FALTA documento: {key}")
                        else:
                            logger.info(f"  • Documento verificado ✅: {key}")
                    else:
                        logger.info(f"  • No hay mapeo para: {norm}, verificando directamente")
                        if not user.documents.get(norm):
                            missing.append(req)
                            logger.info(f"  • FALTA documento sin mapeo: {norm}")
                        else:
                            logger.info(f"  • Documento verificado ✅: {norm}")
                
                if missing:
                    logger.info(f"[SKIP] Vacante omitida por faltar: {missing}")
                    logger.info(f"Documentos disponibles: {list(user.documents.keys())}")
                    logger.info(f"Documentos requeridos: {offer_required_docs}")
                    continue  # Saltar a la siguiente vacante
                # Si no falta nada, procesar la vacante normalmente (enviar email, simular, etc)
                # ... (resto del procesamiento de la vacante) ...
            # Solo en modo test se genera y envía el JSON de vacantes
            if getattr(user, 'test_mode', False):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ofertas_{timestamp}.json"
                filepath = os.path.join("data", filename)
                os.makedirs("data", exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(offers, f, ensure_ascii=False, indent=2)
                doc_summary = {}
                for offer in offers:
                    for doc in offer['required_documents']:
                        if doc not in doc_summary:
                            doc_summary[doc] = 0
                        doc_summary[doc] += 1
                summary_text = f"🎉 Análisis completado!\n\n"
                summary_text += f"📊 Resumen final:\n"
                summary_text += f"- Total ofertas: {len(offers)}\n"
                summary_text += f"- Ofertas con email: {len([o for o in offers if o.get('email')])}\n"
                summary_text += f"- Ofertas sin email: {len([o for o in offers if not o.get('email')])}\n\n"
                summary_text += f"📄 Documentos más requeridos:\n"
                for doc, count in doc_summary.items():
                    summary_text += f"- {doc}: {count} ofertas\n"
                summary_text += f"\n💾 Resultados guardados en: {filepath}"
                await context.bot.send_message(
                    chat_id=user_id,
                    text=summary_text
                )
                with open(filepath, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename=filename
                    )
            # Enviar email de prueba automáticamente con la primera oferta válida
            await self.simulate_application(
                offers,
                user_id,
                context,
                user.email,
                user.email_password
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error durante el scraping: {str(e)}"
            )
        finally:
            self.is_scraping = False

    def logger_info(self, message: str):
        self.logger.info(message)

    def logger_warning(self, message: str):
        self.logger.warning(message)

    def logger_error(self, message: str):
        self.logger.error(message)

    def get_required_attachments(self, offer: Dict, user: UserData, customized_paths: Dict = None) -> List[str]:
        """
        Determina qué documentos adjuntar basándose en los documentos requeridos por la oferta.
        
        Args:
            offer: Datos de la oferta con required_documents
            user: Datos del usuario con documentos subidos
            customized_paths: Documentos personalizados ya generados (incluyendo application_form)
            
        Returns:
            Lista de rutas de archivos a adjuntar
        """
        attachments = []
        customized_paths = customized_paths or {}
        
        # Mapeo de nombres de documentos requeridos a claves internas
        doc_synonyms = {
            'applicationform': 'application_form',
            'application form': 'application_form',
            'standard application form': 'application_form',
            'applicationformenglish': 'application_form',
            'application form (english)': 'application_form',
            'applicationform(english)': 'application_form',
            'standardapplicationform': 'application_form',
            'standard application form (english)': 'application_form',
            'standardapplicationform(english)': 'application_form',
            'cv': 'cv',
            'curriculumvitae': 'cv',
            'resume': 'cv',
            'letterofapplication': 'letter_of_application',
            'letter of application': 'letter_of_application',
            'certificatesanddiplomas': 'degree',
            'certificates and diplomas': 'degree',
            'degrees': 'degree',
            'qualifications': 'degree',
            'degree': 'degree',
            'teachingcouncilregistration': 'tc_registration',
            'teaching council registration': 'tc_registration',
            'religiouseducationcertificate': 'religion_certificate',
            'religious education certificate': 'religion_certificate',
            'religioncertificate': 'religion_certificate',
            'religion certificate': 'religion_certificate',
            'teachingpracticegrades': 'practicas',
            'teaching practice grades': 'practicas',
            'teaching practice': 'practicas',
            'refereesdetails': 'referees',
            'referees details': 'referees',
            'referees': 'referees',
            'references': 'referees',
        }
        
        def normalize(doc):
            return doc.lower().replace(' ', '').replace('-', '').replace('_', '')
        
        # Obtener documentos requeridos de la oferta
        required_docs = offer.get('required_documents', [])
        
        # Si no hay documentos requeridos específicos, usar documentos básicos
        if not required_docs:
            self.logger.info("No se especificaron documentos requeridos, usando documentos básicos")
            basic_docs = ['application_form', 'letter_of_application', 'cv', 'degree']
            for doc_key in basic_docs:
                if user.documents.get(doc_key):
                    doc_path = user.documents[doc_key]
                    # Manejar caso donde doc_path puede ser un diccionario
                    if isinstance(doc_path, dict):
                        doc_path = doc_path.get('path', doc_path)
                    if doc_path and os.path.exists(doc_path):
                        attachments.append(doc_path)
            return attachments
        
        # Procesar cada documento requerido
        for req_doc in required_docs:
            norm = normalize(req_doc)
            if norm in doc_synonyms:
                doc_key = doc_synonyms[norm]
                # Para application form, usar el personalizado si existe en customized_paths
                if doc_key == 'application_form':
                    if 'application_form' in customized_paths:
                        form_path = customized_paths['application_form']
                        if form_path and os.path.exists(form_path):
                            # Solo añadir si no está ya en attachments
                            if form_path not in attachments:
                                attachments.append(form_path)
                                self.logger.info(f"Adjuntando {req_doc} -> application_form personalizado")
                    else:
                        self.logger.warning(f"Application Form requerido pero no disponible en customized_paths")
                    continue
                
                # Verificar si el usuario tiene el documento
                if user.documents.get(doc_key):
                    doc_path = user.documents[doc_key]
                    # Manejar caso donde doc_path puede ser un diccionario
                    if isinstance(doc_path, dict):
                        doc_path = doc_path.get('path', doc_path)
                    if doc_path and os.path.exists(doc_path):
                        attachments.append(doc_path)
                        self.logger.info(f"Adjuntando {req_doc} -> {doc_key}")
                    else:
                        self.logger.warning(f"Documento {req_doc} no encontrado en: {doc_path}")
                else:
                    self.logger.warning(f"Usuario no tiene documento requerido: {req_doc}")
            else:
                self.logger.warning(f"Documento requerido no reconocido: {req_doc}")
        
        # Añadir documentos personalizados si existen (excepto application_form que ya se manejó)
        for doc_type, path in customized_paths.items():
            if doc_type != 'application_form' and path and os.path.exists(path):
                attachments.append(path)
                self.logger.info(f"Adjuntando documento personalizado: {doc_type}")
        
        return attachments

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Activa el modo test para el usuario actual"""
        user_id = update.effective_user.id
        if user_id not in self.user_data:
            await update.message.reply_text("❌ Error: Por favor, inicia el proceso con /start")
            return
        user = self.user_data[user_id]
        user.test_mode = True
        await update.message.reply_text(
            "🧪 Modo test activado. Las aplicaciones se redirigirán al email de prueba "
            f"sin consumir cuota de producción, con un máximo de {self.send_policy.batch_limit} "
            f"emails por lote, {self.send_policy.min_interval_seconds} segundos entre envíos y "
            f"{self.send_policy.batch_pause_seconds} segundos de pausa entre lotes."
        )

    def clean_temp_folder(self):
        """Elimina todo el contenido de la carpeta temp evitando afectar los documentos originales."""
        try:
            import shutil, os
            if os.path.isdir('temp'):
                shutil.rmtree('temp')
            os.makedirs('temp', exist_ok=True)
            self.logger.info("Carpeta temp limpiada tras finalizar todos los envíos.")
        except Exception as e:
            self.logger.warning(f"Error limpiando carpeta temp: {e}")

    def get_offer_id(self, offer: Dict) -> str:
        """Devuelve un ID único de la oferta para registrar/consultar en Firebase."""
        return offer.get('id') or offer.get('vacancy_id') or offer.get('url', '').split('/')[-1] or 'unknown'
