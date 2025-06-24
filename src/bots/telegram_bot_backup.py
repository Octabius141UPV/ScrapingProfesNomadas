#!/usr/bin/env python3
"""
Bot de Telegram para gestionar documentos
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
import json
from typing import Dict, Callable, List
import aiofiles
import sys
import asyncio
from datetime import datetime

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.document_reader import DocumentReader
from src.utils.pdf_generator import PDFGenerator
from src.utils.document_validator import DocumentValidator
from src.scrapers.scraper_educationposts import EducationPosts
import traceback
from src.utils.firebase_manager import get_applied_vacancies, mark_vacancy_as_applied

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID del usuario autorizado
AUTHORIZED_USER_IDS = [1070017515, 7034549850]

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
        self.state = "waiting_name"
        self.previous_state = None
        self.county_selection = None  # "cork", "dublin", "both"
        self.dublin_zone = None  # "north", "south", "west", "city_center", "all"
        self.education_level = None  # "primary", "post_primary", "pre_school", etc.
        self.education_level_id = None  # ID para el scraper
        self.referentes_sent = False  # Controla si ya se envió el Excel de referentes
        self.practicas_sent = False   # Controla si ya se envió el Excel de prácticas
        
        # Solo el atributo que realmente causa el error
        self.teaching_council_registration = None

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

class TelegramBot:
    def __init__(self, token: str):
        """
        Inicializa el bot de Telegram
        
        Args:
            token: Token de autenticación del bot
        """
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Obtener lista de usuarios autorizados (usar la variable global o el .env)
        try:
            authorized_ids_env = os.getenv('AUTHORIZED_USER_IDS', '')
            if authorized_ids_env:
                # Si hay un valor en .env, usarlo (formato: "id1,id2,id3")
                self.authorized_user_ids = [int(id_str.strip()) for id_str in authorized_ids_env.split(',')]
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
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_county_selection, pattern="^(cork|dublin|ambos|toda irlanda)$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_dublin_zone_selection, pattern="^dublin_(1|2|3|4|5|6|6w|7|8|9|10|11|12|13|14|15|16|17|18|20|22|23|24|all)$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_education_level_selection, pattern="^(pre-school|primary|post-primary)$"))
        
        # Configurar manejador de errores
        self.application.add_error_handler(self.error_handler)
        
        # Inicializar validadores
        self.document_validator = DocumentValidator()
        self.pdf_generator = PDFGenerator()
        self.document_reader = DocumentReader()
        
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
            "Este bot te ayudará a realizar búsquedas de ofertas educativas en Irlanda y enviar tus aplicaciones.\n\n"
            "📋 Proceso simplificado:\n"
            "1. Proporciona tu nombre y correo electrónico\n"
            "2. Indica si tienes Teaching Council Number\n"
            "3. Sube tus documentos (asegúrate de nombrarlos correctamente)\n"
            "4. Selecciona condado y nivel educativo para buscar ofertas\n\n"
            "📝 IMPORTANTE: Nombra tus documentos incluyendo estas palabras exactas:\n\n"
            "📄 Documentos OBLIGATORIOS:\n"
            "• Letter of Application (nombre debe contener 'letter of application')\n"
            "• CV (nombre debe contener 'cv')\n"
            "• Título universitario (nombre debe contener 'degree')\n"
            "• Application Form (.pdf) (nombre debe contener 'application form')\n"
            "• Teaching Practice (.docx recomendado) (nombre debe contener 'teaching practice')\n"
            "• Referees (.docx recomendado) (nombre debe contener 'referees')\n\n"
            "📄 Documentos OPCIONALES:\n"
            "• Certificado de registro TC (nombre debe contener 'tc registration')\n"
            "• Certificado de religión (nombre debe contener 'religion')\n\n"
            "💡 IMPORTANTE: Se requiere formato .pdf para Application Form y se recomienda .docx para Teaching Practice y Referees Details para permitir la personalización automática con los datos de cada oferta.\n\n"
            "Por favor, envía tu nombre completo:"
        )
        
        await update.message.reply_text(welcome_message)
        self.user_data[user_id].state = "waiting_name"
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /help"""
        if not await self.is_authorized(update):
            return
        
        help_text = (
            "📚 **GUÍA DE DOCUMENTOS**\n\n"
            "Para que el sistema reconozca automáticamente tus documentos, incluye estas palabras en el nombre del archivo:\n\n"
            "📄 **Documentos Obligatorios:**\n"
            "• Para Letter of Application: 'letter of application', 'carta', 'application letter' o 'cover letter'\n"
            "• Para CV: 'cv', 'curriculum', 'resume' o 'resumen'\n"
            "• Para Degree: 'degree', 'titulo', 'certificate', 'diploma' o 'qualification'\n"
            "• Para Standard Application Form (.pdf): 'application form', 'formulario', 'standard' o 'template'\n"
            "• Para Teaching Practice (.docx recomendado): 'teaching practice', 'practicas', 'practices' o 'placement'\n"
            "• Para Referees (.docx recomendado): 'referees', 'references', 'referentes' o 'referencia'\n\n"
            "📄 **Documentos Opcionales:**\n"
            "• Para Teaching Council Registration: 'tc registration', 'teaching council' o 'registration'\n"
            "• Para Religion Certificate: 'religion', 'religious', 'catequesis' o 'catequista'\n\n"
            "IMPORTANTE: Se requiere formato .pdf para Application Form y se recomienda .docx para Teaching Practice y Referees Details para permitir la personalización automática con los datos de cada oferta.\n\n"
            "💡 **Consejo:** Si tienes problemas con el reconocimiento, asegúrate de que el nombre del archivo contenga al menos una de las palabras clave mencionadas."
        )
        
        await update.message.reply_text(help_text)
    
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
            
            # Validar tipo de archivo para los documentos que deben ser PDF
            is_application_form = any(keyword in file_name for keyword in ['application form', 'formulario', 'template', 'applicationform'])
            is_teaching_practice = any(keyword in file_name for keyword in ['teaching practice', 'practicas', 'practices', 'placement'])
            is_referees = any(keyword in file_name for keyword in ['referees', 'references', 'referentes', 'referencia'])
            
            # Para Application Form, Teaching Practice y Referees, permitir .pdf para Application Form y .docx para los otros (para personalización) o PDF
            if is_application_form:
                if not file_name.endswith('.pdf'):
                    await update.message.reply_text(
                        f"❌ El documento {document_type} debe estar en formato .pdf.\n\n"
                        f"👉 Para aprovechar la personalización automática con los datos de la oferta, sube el documento en formato .pdf."
                    )
                    return
            elif is_teaching_practice or is_referees:
                if not (file_name.endswith('.docx') or file_name.endswith('.pdf')):
                    document_type = "Teaching Practice" if is_teaching_practice else "Referees"
                    await update.message.reply_text(
                        f"❌ El documento {document_type} debe estar en formato .docx (recomendado para personalización automática) o .pdf.\n\n"
                        f"👉 Para aprovechar la personalización automática con los datos de la oferta, sube el documento en formato .docx."
                    )
                    return
            
            # Crear directorio temporal si no existe
            os.makedirs("temp", exist_ok=True)
            temp_path = os.path.join("temp", file_name)
            
            # Descargar el archivo
            await file.download_to_drive(temp_path)
            
            # Determinar el tipo de documento
            doc_type = None
            file_name_lower = file_name.lower()
            
            # Mapeo de palabras clave a tipos de documento
            doc_keywords = {
                'letter_of_application': ['letter of application', 'letterofapplication'],
                'cv': ['cv', 'curriculum', 'resume'],
                'degree': ['degree', 'titulo', 'universidad', 'universitario'],
                'application_form': ['application form', 'formulario', 'template', 'applicationform', 'standard'],
                'teaching_practice': ['teaching practice', 'practicas', 'practices', 'placement'],
                'referees': ['referees', 'references', 'referentes', 'referencia'],
                'tc_registration': ['tc', 'registration', 'teaching council'],
                'religion_certificate': ['religion', 'religious', 'certificate']
            }
            
            # Buscar coincidencias en el nombre del archivo
            for doc_type_key, keywords in doc_keywords.items():
                if any(keyword in file_name_lower for keyword in keywords):
                    doc_type = doc_type_key
                    break
                    
            # Caso especial: "letter of application def adc" debe procesarse como Letter of Application, no Application Form
            if 'letter of application def adc' in file_name_lower or ('letter of application' in file_name_lower and 'def adc' in file_name_lower):
                doc_type = 'letter_of_application'
                await update.message.reply_text(
                    "ℹ️ He identificado que el archivo 'Letter of Application def AdC' es una carta de presentación. "
                    "Lo procesaré como Letter of Application."
                )
            
            if doc_type:
                # Guardar el documento
                user.documents[doc_type] = {
                    'path': temp_path,
                    'filename': file_name
                }
                
                # Actualizar atributos adicionales para compatibilidad
                if doc_type == 'tc_registration':
                    user.teaching_council_registration = True
                    logger.info(f"Usuario {user_id} subió documento TC Registration, actualizando teaching_council_registration=True")
                
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
                    message = f"✅ {file_name} guardado correctamente.\n\n"
                    
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
            self.user_data[user_id].state = "waiting_name"
        
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
            # Ya no necesitamos guardar estos campos adicionales
            tc_registration = message_text.lower() == "sí" or message_text.lower() == "si"
            user.teaching_council_registration = tc_registration  # Actualizar el atributo para compatibilidad
            logger.info(f"Usuario {user_id} tiene TC registration: {tc_registration}")
            
            # Pasar directamente al estado waiting_documents
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
            
            # Si se han enviado los documentos, permitir selección de condado
            if user.has_required_documents():
                await update.message.reply_text(
                    "Por favor, selecciona el condado donde quieres buscar:\n"
                    "• Cork\n"
                    "• Dublin"
                )
                user.state = "waiting_county"
        
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            school_name = offer.get('school_name', 'School').replace(' ', '_').lower()
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

    async def send_application_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Envía el email de aplicación"""
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
                            f"📌 Escuela: {offer_data['school_name']}\n"
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
                            f"📌 Escuela: {offer_data['school_name']}\n"
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
        attachments = [form_path]  # Siempre incluir el formulario PDF generado
        
        # Obtener documentos requeridos y adjuntarlos
        required_attachments = self.get_required_attachments(offer, user, customized_paths)
        attachments.extend(required_attachments)
        
        # Log de documentos adjuntados
        self.logger.info(f"Documentos adjuntados para {offer.get('school_name', 'School')}:")
        self.logger.info(f"- Application Form: {form_path}")
        for doc_path in required_attachments:
            self.logger.info(f"- {os.path.basename(doc_path)}")
        
        # Añadir documentos personalizados si existen
        for doc_type, path in customized_paths.items():
            attachments.append(path)
        
        # Añadir documentos obligatorios
        if user.documents['letter_of_application']:
            attachments.append(user.documents['letter_of_application'])
        if user.documents['cv']:
            attachments.append(user.documents['cv'])
        if user.documents['degree']:
            attachments.append(user.documents['degree'])
            
        # Añadir documentos opcionales si existen
        if user.documents['tc_registration']:
            attachments.append(user.documents['tc_registration'])
        if user.documents['religion_certificate']:
            attachments.append(user.documents['religion_certificate'])
            
        # Añadir Teaching Practice si existe y no se personalizó como .docx
        if user.documents['teaching_practice'] and 'teaching_practice' not in customized_paths:
            attachments.append(user.documents['teaching_practice'])
        
        # Añadir Referees si existe y no se personalizó como .docx
        if user.documents['referees'] and 'referees' not in customized_paths:
            attachments.append(user.documents['referees'])
                
        # Generar PDFs de Excel si existen
        if user.documents['practicas']:
            practicas_pdf = await pdf_generator.generate_practicas_pdf(user.documents['practicas'])
            if practicas_pdf:
                attachments.append(practicas_pdf)
                
        if user.documents['referentes']:
            referentes_pdf = await pdf_generator.generate_referentes_pdf(user.documents['referentes'])
            if referentes_pdf:
                attachments.append(referentes_pdf)
                
        # Preparar el cuerpo del email
        email_body = f"""
Dear {offer['school_name']} Hiring Committee,

I am writing to express my interest in the {offer['position']} position advertised on EducationPosts.ie.

I have attached my application form along with all required documents:
- Application Form
- Letter of Application
- CV
- Degree Certificate
{f"- Teaching Council Registration" if user.documents['tc_registration'] else ""}
{f"- Religion Certificate" if user.documents['religion_certificate'] else ""}
{f"- Teaching Experience" if user.documents['practicas'] else ""}
{f"- References" if user.documents['referentes'] else ""}

I meet all the requirements for this position and am available for an interview at your convenience.

Best regards,
{user.name}
{user.email}
"""
        
        # Enviar el email
        try:
            await self.email_sender.send_email(
                to_email=offer['email'],
                subject=f"Application for {offer['position']} - {user.name}",
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
            
        finally:
            # Limpiar archivos temporales
            for attachment in attachments:
                try:
                    os.remove(attachment)
                except:
                    pass

    async def send_test_email(self, offer: Dict, from_email: str, from_password: str) -> bool:
        """
        Envía un email de prueba a raulforteabusiness@gmail.com con los detalles de la oferta.
        """
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders
            import os

            # Filtro de emails genéricos
            BAD_MAILS = ["noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie"]
            school_email = offer.get('email', '').lower()
            if not school_email or any(bad in school_email for bad in BAD_MAILS):
                self.logger.warning(f"Email de la oferta no válido o genérico: {school_email}. No se enviará email de prueba.")
                return False

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
            msg['Subject'] = f"[TEST] Application for {offer.get('vacancy', 'Teaching Position')} at {offer.get('school', 'School')}"

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
            # Aquí ya es seguro acceder a user.name, user.email, user.documents, etc.
            despedida = f"Kind regards,\n{user.name}\n{user.email}"
            body = f"""
            Dear Hiring Manager at {offer.get('school', 'the school')},

            I am writing to express my strong interest in the position of {offer.get('vacancy', 'Teaching Position')} recently advertised.

            Please find attached the required documents for this application:
            {doc_lines}

            - Requirements: {requirements}

            I look forward to the opportunity to discuss my application further.

            {despedida}
            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

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
                'teachingpracticegrades': 'practicas',
                'teaching practice grades': 'practicas',
                'refereesdetails': 'referentes',
                'referees': 'referentes',
                'references': 'referentes',
            }
            def normalize(doc):
                return doc.lower().replace(' ', '').replace('-', '').replace('_', '')

            # Adjuntar documentos requeridos (incluyendo el application form generado)
            docs_faltantes = []
            for req in required_docs:
                norm = normalize(req)
                if norm in doc_synonyms:
                    key = doc_synonyms[norm]
                    if key is None:
                        # Generar y adjuntar el application form usando la plantilla del usuario
                        form_path = await self.generate_application_form(offer, user)
                        if form_path and os.path.exists(form_path):
                            with open(form_path, 'rb') as f:
                                part = MIMEBase('application', 'pdf')
                                part.set_payload(f.read())
                                encoders.encode_base64(part)
                                part.add_header('Content-Disposition', f'attachment; filename=application_form.pdf')
                                msg.attach(part)
                        else:
                            docs_faltantes.append(req)
                        continue
                    if not user.documents.get(key):
                        docs_faltantes.append(req)
                else:
                    # Si no está en el mapeo, buscar coincidencia directa en user.documents
                    if not user.documents.get(norm):
                        docs_faltantes.append(req)
            if docs_faltantes:
                self.logger.warning(f"Faltan documentos requeridos para la vacante: {docs_faltantes}. No se enviará el email.")
                return False

            # Conectar al servidor SMTP de Gmail
            self.logger.info(f"Conectando a SMTP: smtp.gmail.com:587")
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            self.logger.info(f"Iniciando sesión con: {from_email}")
            server.login(from_email, from_password)
            self.logger.info(f"Enviando email a: raulforteabusiness@gmail.com")
            server.send_message(msg)
            server.quit()
            self.logger.info("Email enviado correctamente")
            return True
        except Exception as e:
            self.logger.error(f"Error enviando email de prueba: {str(e)}")
            return False

    async def simulate_application(self, offers: List[Dict], user_id: int, context, from_email: str, from_password: str) -> None:
        """
        Simula el envío de una solicitud a la primera oferta válida (que tenga email)
        
        Args:
            offers: Lista de ofertas
            user_id: ID del usuario de Telegram
            context: Contexto del bot
            from_email: Email de origen
            from_password: Contraseña del email de origen
        """
        if not offers:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ No hay ofertas para simular el envío."
            )
            return
            
        # Obtener la primera oferta válida (que tenga email y no sea genérico)
        BAD_MAILS = ["noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie"]
        valid_offers = [o for o in offers if o.get('email') and not any(bad in o.get('email', '').lower() for bad in BAD_MAILS)]
        if not valid_offers:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ No hay ofertas con email válido para simular el envío."
            )
            return
        offer = valid_offers[0]
        
        # Preparar mensaje de simulación
        sim_msg = "📧 Preparando envío de email de prueba:\n\n"
        sim_msg += f"🏫 Escuela: {offer.get('school', 'N/A')}\n"
        sim_msg += f"📝 Vacante: {offer.get('vacancy', 'N/A')}\n"
        sim_msg += f"📧 Email destino: raulforteabusiness@gmail.com\n"
        sim_msg += f"📧 Email origen: {from_email}\n\n"
        
        if offer['required_documents']:
            sim_msg += "📄 Documentos requeridos:\n"
            for doc in offer['required_documents']:
                sim_msg += f"- {doc}\n"
        else:
            sim_msg += "⚠️ No se especificaron documentos requeridos\n"
            
        # Enviar mensaje de simulación
        await context.bot.send_message(
            chat_id=user_id,
            text=sim_msg
        )
        
        # Enviar email de prueba
        success = await self.send_test_email(
            offer=offer,
            from_email=from_email,
            from_password=from_password
        )
        
        if success:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Email de prueba enviado correctamente:\n"
                     "📧 Email enviado a raulforteabusiness@gmail.com\n"
                     "📎 Incluye todos los detalles de la oferta\n"
                     "🔍 [TEST] en el asunto del email"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Error al enviar el email de prueba. Por favor, verifica las credenciales."
            )

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
        level_map = {"pre-school": "pre_school", "primary": "primary", "second_level": "second_level"}
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
                "22": "Dublin 22", "23": "Dublin 23", "24": "Dublin 24", "all": "Todo Dublin"
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
                        district_offers = await scraper.fetch_all(limit=5)  # Limitamos a 5 por distrito para evitar sobrecarga
                        
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
                    offers = await scraper.fetch_all(limit=10)
            else:
                # Para Cork o todo Dublin, usar el scraper normal
                scraper = EducationPosts(level=level, county_id=county_id, district_id="")
                offers = await scraper.fetch_all(limit=10)
                
            if not offers:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ No se encontraron ofertas educativas."
                )
                return
            # --- INTEGRACIÓN FIREBASE: filtrar ofertas ya aplicadas ---
            applied_ids = get_applied_vacancies(user.email)
            offers = [o for o in offers if o.get('url') and o['url'] not in applied_ids]
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
            customized_paths: Documentos personalizados ya generados
            
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
        
        # Obtener documentos requeridos de la oferta
        required_docs = offer.get('required_documents', [])
        
        # Si no hay documentos requeridos específicos, usar documentos básicos
        if not required_docs:
            self.logger.info("No se especificaron documentos requeridos, usando documentos básicos")
            basic_docs = ['application_form', 'letter_of_application', 'cv', 'degree']
            for doc_key in basic_docs:
                if user.documents.get(doc_key):
                    doc_path = user.documents[doc_key]['path'] if isinstance(user.documents[doc_key], dict) else user.documents[doc_key]
                    if doc_path and os.path.exists(doc_path):
                        attachments.append(doc_path)
            return attachments
        
        # Procesar cada documento requerido
        for req_doc in required_docs:
            norm = normalize(req_doc)
            
            if norm in doc_synonyms:
                doc_key = doc_synonyms[norm]
                
                # Para application form, usar el personalizado si existe
                if doc_key == 'application_form':
                    # El application form se maneja por separado, no lo incluimos aquí
                    continue
                
                # Verificar si el usuario tiene el documento
                if user.documents.get(doc_key):
                    doc_path = user.documents[doc_key]['path'] if isinstance(user.documents[doc_key], dict) else user.documents[doc_key]
                    if doc_path and os.path.exists(doc_path):
                        attachments.append(doc_path)
                        self.logger.info(f"Adjuntando {req_doc} -> {doc_key}")
                    else:
                        self.logger.warning(f"Documento {req_doc} no encontrado en: {doc_path}")
                else:
                    self.logger.warning(f"Usuario no tiene documento requerido: {req_doc}")
            else:
                self.logger.warning(f"Documento requerido no reconocido: {req_doc}")
        
        # Añadir documentos personalizados si existen
        for doc_type, path in customized_paths.items():
            if path and os.path.exists(path):
                attachments.append(path)
                self.logger.info(f"Adjuntando documento personalizado: {doc_type}")
        
        return attachments
