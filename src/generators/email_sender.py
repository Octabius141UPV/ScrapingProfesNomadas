import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import html
import os
import base64
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
            
    async def send_application_email(self, user_data: Dict, offer: Dict, excel_path: str = None, application_form_pdf: str = None, body: str = None, subject: str = None) -> bool:
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
            subject = subject or self._generate_subject(user_data, offer)
            
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
                    tc_route = user_data.get('tc_route', '1')  # Default a ruta 1 si no se especifica
                    if tc_number:
                        tc_info_text = f"I already possess the Teaching Council Number route {tc_route} ({tc_number})."
                        logger.info(f"TC Number extraído del PDF: {tc_number}")
                    else:
                        # Fallback si no se puede extraer el número del PDF
                        tc_info_text = "I have attached my Teaching Council registration."
                        logger.info("No se pudo extraer el TC Number del PDF. Usando texto genérico.")
            # Si no hay documento, usar el número de TC si está en los datos del usuario
            elif user_data.get('teaching_council_registration'):
                tc_number = user_data.get('teaching_council_registration')
                tc_route = user_data.get('tc_route', '1')  # Default a ruta 1 si no se especifica
                tc_info_text = f"I already possess the Teaching Council Number route {tc_route} ({tc_number})."
                logger.info(f"Usando TC Number de los datos de usuario: {tc_number}")

            # Reemplazar la sección del TC en la plantilla
            if tc_info_text:
                full_sentence = f"I am {user_data.get('name', '[nombre]')}, a Primary Education Teacher. {tc_info_text}"
                formatted_template = template.replace(
                    "I am [nombre], a Primary Education Teacher. [I already possess the Teaching Council Number (en caso de que ya lo tengan)]",
                    full_sentence
                )
            else:
                # Si no hay información del TC, quitar la parte opcional
                formatted_template = template.replace(
                    "I am [nombre], a Primary Education Teacher. [I already possess the Teaching Council Number (en caso de que ya lo tengan)]",
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
            path = document['path']
            filename = document.get('filename') or os.path.basename(path) or 'attachment'
            # Si el archivo es PDF por ruta o nombre, asegura extensión .pdf
            if (path.lower().endswith('.pdf') or filename.lower().endswith('.pdf')) and not filename.lower().endswith('.pdf'):
                filename += '.pdf'

            # Detectar tipo MIME
            guessed_type = mimetypes.guess_type(filename)[0] or mimetypes.guess_type(path)[0]
            if guessed_type:
                maintype, subtype = guessed_type.split('/', 1)
            else:
                maintype, subtype = ('application', 'octet-stream')

            with open(path, 'rb') as attachment:
                part = MIMEBase(maintype, subtype)
                part.set_payload(attachment.read())

            encoders.encode_base64(part)
            # Content-Disposition con filename correcto evita "noname"
            part.add_header('Content-Disposition', 'attachment', filename=filename)

            msg.attach(part)
            logger.info(f"Documento adjuntado: {filename}")
            
        except Exception as e:
            try:
                fn = document.get('filename', 'attachment')
            except Exception:
                fn = 'attachment'
            logger.error(f"Error adjuntando documento {fn}: {str(e)}")
            
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

    async def send_presentation_email(
        self,
        from_email: Optional[str],
        from_password: Optional[str],
        to_email: str,
        presentation_pdf_path: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        *,
        resend_api_key: Optional[str] = None,
        resend_from_email: Optional[str] = None,
    ) -> bool:
        """Envía la presentación usando Resend en lugar de SMTP clásico.

        Args:
            from_email: Dirección visible del remitente (se usa como fallback si no se especifica ``resend_from_email``)
            from_password: Ya no se utiliza; se mantiene por compatibilidad
            to_email: Destinatario
            presentation_pdf_path: Ruta al PDF a adjuntar
            subject: Asunto opcional
            body: Cuerpo opcional (texto plano UTF-8)
            resend_api_key: API Key de Resend (opcional, por defecto se lee de ``RESEND_API_KEY``)
            resend_from_email: Remitente verificado en Resend (opcional, fallback a ``from_email`` o ``RESEND_FROM_EMAIL``)
        """
        try:
            if not os.path.exists(presentation_pdf_path):
                logger.error(f"PDF de presentación no encontrado: {presentation_pdf_path}")
                return False

            api_key = resend_api_key or os.getenv("RESEND_API_KEY")
            if not api_key:
                logger.error("Resend no está configurado. Define RESEND_API_KEY o pasa 'resend_api_key'.")
                return False

            sender_address = resend_from_email or from_email or os.getenv("RESEND_FROM_EMAIL")
            if not sender_address:
                logger.error("Falta la dirección remitente para Resend. Configura RESEND_FROM_EMAIL o pásala como argumento.")
                return False

            default_body = (
                "Dear School Team,\n\n"
                "I hope you are well. We are Profes Nómadas, a service that helps schools streamline teacher applications and communication. "
                "Please find attached a short presentation with our details.\n\n"
                "Kind regards,\nProfes Nómadas"
            )
            plain_text = body or default_body
            html_text = html.escape(plain_text).replace('\n', '<br>')
            html_body = (
                "<div style=\"font-family:Arial,Helvetica,sans-serif; white-space:pre-wrap;\">"
                f"{html_text}"
                "</div>"
            )

            attachment_name = os.path.basename(presentation_pdf_path) or 'ProfesNomadas_Presentation.pdf'
            if not attachment_name.lower().endswith('.pdf'):
                attachment_name += '.pdf'

            with open(presentation_pdf_path, "rb") as pdf_file:
                encoded_pdf = base64.b64encode(pdf_file.read()).decode("ascii")

            payload: Dict[str, Any] = {
                "from": sender_address,
                "to": [to_email],
                "subject": subject or "Presentation – Profes Nómadas",
                "html": html_body,
                "text": plain_text,
                "attachments": [
                    {
                        "filename": attachment_name,
                        "content": encoded_pdf,
                        "mime_type": "application/pdf",
                    }
                ],
            }

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._send_presentation_via_resend, payload, api_key)
        except Exception as e:
            logger.error(f"Error enviando presentación: {str(e)}")
            return False

    def _send_presentation_via_resend(self, payload: Dict[str, Any], api_key: str) -> bool:
        """Ejecuta el envío a través de Resend en un hilo separado."""
        try:
            import resend  # type: ignore[import]
        except ImportError:
            logger.error("La librería 'resend' no está instalada. Añádela a los requisitos o ejecuta 'pip install resend'.")
            return False

        try:
            resend.api_key = api_key
            response = resend.Emails.send(payload)
            resend_id = None
            try:
                resend_id = response.get('id') if isinstance(response, dict) else getattr(response, 'id', None)
            except Exception:
                resend_id = getattr(response, 'id', None)
            logger.info("Presentación enviada con Resend", extra={"resend_id": resend_id})
            return True
        except Exception as exc:
            logger.error(f"Error enviando email con Resend: {exc}")
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
