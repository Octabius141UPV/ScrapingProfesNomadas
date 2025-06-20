import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Dict, List, Optional, Any
import asyncio
import re
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        # Las credenciales se proporcionarán por usuario
        self.email_address = None
        self.email_password = None
            
    async def send_application_email(self, user_data: Dict, offer: Dict, excel_path: str = None, application_form_pdf: str = None, body: str = None) -> bool:
        """
        Envía un email de solicitud personalizado para una oferta específica
        
        Args:
            user_data: Datos del usuario
            offer: Datos de la oferta
            excel_path: Path al archivo Excel (opcional)
            application_form_pdf: Path al PDF del application form personalizado (opcional)
            body: Cuerpo personalizado del email (opcional)
        """
        try:
            # Configurar credenciales del usuario
            self.email_address = user_data.get('email')
            self.email_password = user_data.get('email_password')
            
            if not self.email_address or not self.email_password:
                logger.error("Credenciales de email no proporcionadas por el usuario")
                return False
            
            # Ya no usamos perfil de usuario basado en AI
            
            # Generar contenido del email
            subject = self._generate_subject(user_data, offer)
            
            # Usar el body proporcionado si existe, si no, generar como antes
            if body is not None:
                email_body = body
            else:
                email_body = self._generate_email_body_static(user_data, offer)
            logger.info("Email generado con template estático" if body is None else "Email generado con body personalizado")
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = offer['email']
            msg['Subject'] = subject
            
            # Adjuntar cuerpo del mensaje
            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
            
            # Adjuntar documentos si existen
            if user_data.get('documents'):
                for doc in user_data['documents']:
                    if os.path.exists(doc['path']):
                        self._attach_document(msg, doc)
            
            # Adjuntar PDF del application form personalizado si se proporciona
            if application_form_pdf and os.path.exists(application_form_pdf):
                pdf_doc = {
                    'path': application_form_pdf,
                    'filename': f"Application_Form_{offer.get('school_name', 'School').replace(' ', '_')}.pdf"
                }
                self._attach_document(msg, pdf_doc)
                logger.info(f"Application form PDF personalizado adjuntado: {pdf_doc['filename']}")
            
            # Enviar email
            success = await self._send_email(msg, offer['email'])
            
            if success:
                logger.info(f"Email enviado exitosamente a {offer['school_name']} ({offer['email']})")
            else:
                logger.error(f"Error enviando email a {offer['school_name']}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error generando email para {offer.get('school_name', 'Unknown')}: {str(e)}")
            return False
            
    def _generate_subject(self, user_data: Dict, offer: Dict) -> str:
        """Genera el asunto del email"""
        return f"Application – {user_data['name']}"
        
    def _generate_email_body_static(self, user_data: Dict, offer: Dict) -> str:
        """
        Genera el cuerpo del email usando el template estático (fallback)
        """
        try:
            # Cargar template
            template_path = "templates/email_template.txt"
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
            else:
                # Template por defecto si no existe el archivo
                template = self._get_default_template()
            
            # Inicializar variables para el TC
            tc_info_text = ""
            
            # Verificar si hay documentos de TC
            tc_document_path = None
            if user_data.get('documents') and isinstance(user_data['documents'], dict):
                tc_doc = user_data['documents'].get('tc_registration')
                if isinstance(tc_doc, dict) and tc_doc.get('path'):
                    tc_document_path = tc_doc['path']
                elif isinstance(tc_doc, str):
                    tc_document_path = tc_doc

            # Determinar el texto del TC basado en el documento
            if tc_document_path and os.path.exists(tc_document_path):
                # Comprobar si es una imagen
                if any(tc_document_path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
                    tc_info_text = "My Teaching Council registration is currently being processed."
                    logger.info("TC Registration es una imagen. Usando texto de 'en trámite'.")
                # Si es un PDF, intentar extraer el número
                elif tc_document_path.lower().endswith('.pdf'):
                    tc_number = self._extract_tc_number_from_pdf(tc_document_path)
                    if tc_number:
                        tc_info_text = f"I already possess the Teaching Council Number route 1 ({tc_number})."
                        logger.info(f"TC Number extraído del PDF: {tc_number}")
                    else:
                        # Fallback si no se puede extraer el número del PDF
                        tc_info_text = "I have attached my Teaching Council registration."
                        logger.info("No se pudo extraer el TC Number del PDF. Usando texto genérico.")
            # Si no hay documento, usar el número de TC si está en los datos del usuario
            elif user_data.get('teaching_council_registration'):
                tc_number = user_data.get('teaching_council_registration')
                tc_info_text = f"I already possess the Teaching Council Number route 1 ({tc_number})."
                logger.info(f"Usando TC Number de los datos de usuario: {tc_number}")

            # Reemplazar la sección del TC en la plantilla
            if tc_info_text:
                full_sentence = f"I am {user_data.get('name', '[nombre]')}, a Primary Education Teacher. {tc_info_text}"
                formatted_template = template.replace(
                    "I am [nombre], a Primary Education Teacher. [I already possess the Teaching Council Number route 1 (en caso de que ya lo tengan)]",
                    full_sentence
                )
            else:
                # Si no hay información del TC, quitar la parte opcional
                formatted_template = template.replace(
                    "I am [nombre], a Primary Education Teacher. [I already possess the Teaching Council Number route 1 (en caso de que ya lo tengan)]",
                    f"I am {user_data.get('name', '[nombre]')}, a Primary Education Teacher."
                )

            # Reemplazar [nombre] donde sea que aparezca en el texto
            formatted_template = formatted_template.replace("[nombre]", user_data.get('name', '[nombre]'))
            
            body = formatted_template.format(
                school_name=offer.get('school_name', 'Your Institution'),
                user_name=user_data['name'],
                user_email=user_data['email'],
                position=offer.get('position', 'teaching position'),
                level=offer.get('level', 'educational'),
                county=offer.get('county', 'Ireland'),
                description=offer.get('description', '')[:200] + "..." if offer.get('description', '') else ''
            )
            
            return body
            
        except Exception as e:
            logger.error(f"Error generando cuerpo del email: {str(e)}")
            return self._get_fallback_email_body(user_data, offer)
            
    def _get_default_template(self) -> str:
        """Template por defecto para emails"""
        return """Dear Hiring Manager at {school_name},

I hope this email finds you well. My name is {user_name}, and I am writing to express my strong interest in the {position} opportunity at your {level} institution in {county}.

I am a qualified educator with a passion for teaching and a commitment to providing excellent educational experiences for students. I believe that my skills and experience would make me a valuable addition to your educational team.

Key highlights of my profile:
• Qualified teaching professional
• Strong commitment to educational excellence  
• Excellent communication and interpersonal skills
• Adaptable and enthusiastic approach to learning
• Experience working in multicultural environments

I am particularly drawn to the opportunity to contribute to the educational mission of {school_name}. I am excited about the possibility of bringing my passion for education to your institution and making a positive impact on student learning.

Please find my CV and supporting documents attached to this email. I would welcome the opportunity to discuss my application further and am available for an interview at your convenience.

Thank you for considering my application. I look forward to hearing from you soon.

Kind regards,

{user_name}
Email: {user_email}

---
This application was sent as part of my job search process in the Irish education sector."""

    def _get_fallback_email_body(self, user_data: Dict, offer: Dict) -> str:
        """Email básico en caso de error con el template"""
        return f"""Dear Hiring Manager,

My name is {user_data['name']}, and I am writing to express my interest in the teaching position at {offer.get('school_name', 'your institution')}.

I am a qualified educator looking for opportunities in the Irish education sector. I believe my skills and passion for teaching would make me a valuable addition to your team.

Please find my CV and supporting documents attached.

Thank you for your consideration.

Best regards,
{user_data['name']}
{user_data['email']}"""

    def _attach_document(self, msg: MIMEMultipart, document: Dict):
        """
        Adjunta un documento al email
        """
        try:
            with open(document['path'], 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {document["filename"]}'
            )
            
            msg.attach(part)
            logger.info(f"Documento adjuntado: {document['filename']}")
            
        except Exception as e:
            logger.error(f"Error adjuntando documento {document['filename']}: {str(e)}")
            
    async def _send_email(self, msg: MIMEMultipart, recipient: str) -> bool:
        """
        Envía el email usando SMTP
        """
        try:
            # Ejecutar en un thread separado para no bloquear
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self._smtp_send, 
                msg, 
                recipient
            )
            return success
            
        except Exception as e:
            logger.error(f"Error en envío asíncrono: {str(e)}")
            return False
            
    def _smtp_send(self, msg: MIMEMultipart, recipient: str) -> bool:
        """
        Función síncrona para envío SMTP
        """
        try:
            # Crear conexión SMTP
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Habilitar encriptación
            server.login(self.email_address, self.email_password)
            
            # Enviar email
            text = msg.as_string()
            server.sendmail(self.email_address, recipient, text)
            server.quit()
            
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("Error de autenticación SMTP. Verifica EMAIL_ADDRESS y EMAIL_PASSWORD")
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.error(f"Destinatario rechazado: {recipient}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"Error SMTP: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error enviando email a {recipient}: {str(e)}")
            return False
            
    async def send_test_email(self, test_recipient: str, email_address: str = None, email_password: str = None) -> bool:
        """
        Envía un email de prueba para verificar configuración
        """
        try:
            # Configurar credenciales si se proporcionan
            if email_address and email_password:
                self.email_address = email_address
                self.email_password = email_password
            
            if not self.email_address or not self.email_password:
                logger.error("Credenciales de email no configuradas para test")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = test_recipient
            msg['Subject'] = "Test Email - ScrapingProfesNomadas"
            
            body = """This is a test email from ScrapingProfesNomadas bot.

If you receive this email, the email configuration is working correctly.

Best regards,
ScrapingProfesNomadas Bot"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            success = await self._send_email(msg, test_recipient)
            
            if success:
                logger.info(f"Email de prueba enviado exitosamente a {test_recipient}")
            else:
                logger.error(f"Error enviando email de prueba a {test_recipient}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error en email de prueba: {str(e)}")
            return False
    
    def _extract_tc_number_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extrae el número de Teaching Council de un PDF de registro TC
        
        Args:
            pdf_path: Ruta al archivo PDF
            
        Returns:
            El número de Teaching Council o None si no se encuentra
        """
        if not os.path.exists(pdf_path) or not pdf_path.lower().endswith('.pdf'):
            logger.warning(f"No se pudo extraer TC Number. El archivo no existe o no es PDF: {pdf_path}")
            return None
            
        try:
            # Leer el PDF
            with open(pdf_path, 'rb') as file:
                pdf = PdfReader(file)
                text = ""
                
                # Extraer texto de todas las páginas
                for page in pdf.pages:
                    text += page.extract_text() or ""
                
                # Buscar patrones comunes de TC Number
                # Formato típico: 123456, 123/456, 1234567, etc.
                patterns = [
                    r'Registration Number[:\s]+([0-9]{6,7})',
                    r'Registration Number[:\s]+([0-9]{3}[/\s][0-9]{3})',
                    r'Teacher Registration Number[:\s]+([0-9]{6,7})',
                    r'Teacher Registration Number[:\s]+([0-9]{3}[/\s][0-9]{3})',
                    r'Teaching Council Number[:\s]+([0-9]{6,7})',
                    r'Teaching Council Number[:\s]+([0-9]{3}[/\s][0-9]{3})',
                    r'TC Number[:\s]+([0-9]{6,7})',
                    r'TC Number[:\s]+([0-9]{3}[/\s][0-9]{3})'
                ]
                
                # Probar cada patrón
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                
                logger.info("No se encontró un formato reconocible de Teaching Council Number")
                return None
                
        except Exception as e:
            logger.error(f"Error extrayendo TC Number del PDF: {str(e)}")
            return None
