import asyncio
import logging
import sys
import os
import shutil

# Agregar el directorio raíz al path para importaciones
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.bots.telegram_bot import TelegramBot
from src.scrapers.scraper_educationposts import EducationPosts
from src.generators.email_sender import EmailSender
from src.generators.ai_email_generator_v2 import AIEmailGeneratorV2
from config import validate_environment, LOG_FORMAT, LOG_LEVEL, LOG_FILE, LOGS_DIR
from dotenv import load_dotenv
from src.utils.document_reader import DocumentReader

# Cargar variables de entorno
load_dotenv()

# Validar configuración
validate_environment()

# Asegurar que el directorio de logs existe
os.makedirs(LOGS_DIR, exist_ok=True)

# Configurar logging
logging.basicConfig(
    format=LOG_FORMAT,
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ScrapingAgent:
    def __init__(self):
        # Inicializar componentes principales
        self.telegram_bot = None
        self.scraper = EducationPosts()
        self.email_sender = None
        self.ai_generator = AIEmailGeneratorV2()
        self.document_reader = DocumentReader()
        
        logger.info("ScrapingAgent inicializado")
        
    def initialize_telegram_bot(self, token: str):
        """Inicializa el bot de Telegram con el token proporcionado"""
        try:
            self.telegram_bot = TelegramBot()
            logger.info("Bot de Telegram inicializado correctamente")
            return True
        except Exception as e:
            logger.error(f"Error inicializando bot de Telegram: {e}")
            return False
    
    def initialize_email_sender(self, smtp_server: str, smtp_port: int, email: str, password: str):
        """Inicializa el email sender con las credenciales proporcionadas"""
        try:
            self.email_sender = EmailSender(smtp_server, smtp_port, email, password)
            logger.info("Email sender inicializado correctamente")
            return True
        except Exception as e:
            logger.error(f"Error inicializando email sender: {e}")
            return False
        
    async def process_user_request(self, user_data):
        """
        Procesa la solicitud del usuario:
        1. Recibe datos del usuario
        2. Hace scraping de ofertas
        3. Genera y envía emails
        4. Reporta resultados
        """
        try:
            logger.info(f"Procesando solicitud para {user_data.get('name', 'Usuario')}")
            
            # 1. Hacer scraping de ofertas educativas
            logger.info("Iniciando scraping de EducationPosts.ie...")
            offers = await self.scraper.scrape_offers()
            
            if not offers:
                return {
                    'success': False,
                    'message': 'No se encontraron ofertas educativas'
                }
            
            logger.info(f"Se encontraron {len(offers)} ofertas")
            
            # 2. Filtrar ofertas que tengan email de contacto
            valid_offers = [offer for offer in offers if offer.get('email')]
            logger.info(f"Ofertas con email válido: {len(valid_offers)}")
            
            # 3. Cargar perfil Excel si está disponible
            excel_profile = {}
            if user_data.get('excel_profile'):
                excel_profile = self.ai_generator.load_excel_profile(user_data['excel_profile'])
                logger.info(f"Perfil Excel cargado: {list(excel_profile.keys())}")
            
            # 4. Generar y enviar emails personalizados
            sent_count = 0
            errors = []
            
            # Crear carpeta para los application forms
            forms_dir = os.path.join(os.path.dirname(__file__), '../../application_forms')
            os.makedirs(forms_dir, exist_ok=True)
            
            # Ruta de la plantilla PDF
            template_pdf = os.path.join(os.path.dirname(__file__), '../../temp/application form álvaro.pdf')
            
            for offer in valid_offers:
                try:
                    # Generar el application form PDF personalizado
                    output_pdf = os.path.join(forms_dir, f"application_form_{offer.get('school_name','').replace(' ','_')}_{offer.get('roll_number','')}.pdf")
                    pdf_path = self.document_reader.customize_application_form_pdf(
                        template_path=template_pdf,
                        output_path=output_pdf,
                        offer_data=offer
                    )
                    
                    # Generar email personalizado usando AI
                    email_content = self.ai_generator.generate_email(
                        job_data=offer,
                        user_data=user_data,
                        excel_profile=excel_profile
                    )
                    
                    # Enviar email con el PDF adjunto
                    email_sent = await self.email_sender.send_application_email(
                        recipient_email=offer['email'],
                        subject=f"Aplicación para {offer['position']} - {offer['school_name']}",
                        email_content=email_content,
                        user_data=user_data,
                        attachments=[pdf_path] if pdf_path else None
                    )
                    
                    if email_sent:
                        sent_count += 1
                        logger.info(f"Email enviado a {offer['school_name']} ({offer['email']}) con application form adjunto")
                    else:
                        errors.append(f"Error enviando email a {offer['school_name']}")
                    
                    # Borrar el PDF generado
                    if pdf_path and os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception as e:
                    error_msg = f"Error con {offer['school_name']}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    
                # Pausa entre envíos para evitar spam
                await asyncio.sleep(3)
            
            return {
                'success': True,
                'sent_count': sent_count,
                'total_offers': len(valid_offers),
                'errors': errors,
                'ai_features': self.ai_generator.get_available_features()
            }
            
        except Exception as e:
            logger.error(f"Error en proceso principal: {str(e)}")
            return {
                'success': False,
                'message': f'Error interno: {str(e)}'
            }

async def main():
    """Función principal para iniciar el agente"""
    logger.info("🚀 Iniciando ScrapingProfesNomadas Agent...")
    
    # Verificar token de Telegram
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN no configurado")
        logger.info("💡 Agrega tu token de Telegram al archivo .env")
        logger.info("   TELEGRAM_BOT_TOKEN=tu_token_aqui")
        return
    
    # Crear e inicializar agente
    agent = ScrapingAgent()
    
    # Inicializar bot de Telegram
    if not agent.initialize_telegram_bot(telegram_token):
        logger.error("❌ No se pudo inicializar el bot de Telegram")
        return
    
    # Verificar características AI disponibles
    ai_features = agent.ai_generator.get_available_features()
    logger.info(f"🧠 Características AI disponibles: {ai_features}")
    
    if ai_features['ai_generation']:
        logger.info("✅ Generación AI activada")
    else:
        logger.warning("⚠️ Generación AI no disponible, usando templates básicos")
    
    if ai_features['excel_support']:
        logger.info("✅ Soporte Excel activado")
    else:
        logger.warning("⚠️ Soporte Excel limitado")
    
    try:
        # Iniciar bot de Telegram
        logger.info("🤖 Iniciando bot de Telegram...")
        await agent.telegram_bot.start(agent.process_user_request)
        
    except KeyboardInterrupt:
        logger.info("👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error ejecutando bot: {e}")
    finally:
        logger.info("🛑 Cerrando ScrapingAgent...")

def run_standalone_scraper():
    """Ejecuta solo el scraper para pruebas"""
    async def test_scraper():
        logger.info("🕷️ Ejecutando scraper standalone...")
        scraper = EducationPosts()
        offers = await scraper.scrape_offers(max_pages=1)
        logger.info(f"📊 Ofertas encontradas: {len(offers)}")
        
        for i, offer in enumerate(offers[:3]):
            logger.info(f"--- Oferta {i+1} ---")
            logger.info(f"Escuela: {offer.get('school_name')}")
            logger.info(f"Posición: {offer.get('position')}")
            logger.info(f"Email: {offer.get('email')}")
    
    asyncio.run(test_scraper())

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--scraper-only':
        run_standalone_scraper()
    else:
        asyncio.run(main())
