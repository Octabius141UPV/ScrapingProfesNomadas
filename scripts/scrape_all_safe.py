#!/usr/bin/env python3
"""
Script para ejecutar el scraper completo de EducationPosts.ie de forma segura
con selección de condados desde Telegram y generación de application forms PDFs.
"""
import asyncio
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import signal
import traceback
import uuid

# Cargar variables de entorno y forzar la sobreescritura
load_dotenv(override=True)


# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scrapers.scraper_educationposts import EducationPosts
from src.bots.telegram_bot import TelegramBot
from src.utils.logger import setup_logger
from src.utils.document_reader import DocumentReader
from src.generators.email_sender import EmailSender
from src.generators.ai_email_generator_v2 import AIEmailGeneratorV2
from src.utils.application_delivery_queue import (
    ApplicationDeliveryQueue,
    DeliveryAttempt,
)

# Configurar logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/scraping_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("scraping_bot")

async def generate_application_forms_from_offers(offers, template_path=None):
    """
    Genera application forms PDFs personalizados para las ofertas encontradas.
    """
    try:
        if not offers:
            logger.warning("No hay ofertas para generar application forms")
            return []
        # Solo usar la plantilla pasada por parámetro
        if not template_path or not os.path.exists(template_path) or not template_path.endswith('.pdf'):
            logger.error("No se proporcionó una plantilla PDF válida. Aborta generación de application forms.")
            return []
        # Crear directorio para los application forms
        output_dir = os.path.join("temp", "application_forms")
        os.makedirs(output_dir, exist_ok=True)
        # Inicializar DocumentReader
        document_reader = DocumentReader()
        scraper = EducationPosts()
        generated_forms = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"📝 Generando application forms PDFs para {len(offers)} ofertas...")
        for i, offer in enumerate(offers):
            try:
                offer_data = scraper.prepare_offer_data_for_application_form(offer)
                school_name_safe = ''.join(c if c.isalnum() else '_' for c in offer_data['school_name'])
                custom_filename = f"Application_Form_{school_name_safe}_{timestamp}_{i+1}.pdf"
                output_path = os.path.join(output_dir, custom_filename)
                result_path = document_reader.customize_application_form_pdf(
                    template_path=template_path,
                    output_path=output_path,
                    offer_data=offer_data
                )
                if result_path:
                    generated_forms.append({
                        'file_path': result_path,
                        'school_name': offer_data['school_name'],
                        'position': offer_data['position'],
                        'roll_number': offer_data['roll_number']
                    })
                    logger.info(f"✅ [{i+1}/{len(offers)}] PDF generado: {custom_filename}")
                else:
                    logger.warning(f"⚠️ No se pudo generar PDF para: {offer_data['school_name']}")
            except Exception as e:
                logger.error(f"❌ Error generando PDF #{i+1}: {str(e)}")
        logger.info(f"🎯 Total PDFs generados: {len(generated_forms)}")
        return generated_forms
    except Exception as e:
        logger.error(f"Error en generación de application forms: {str(e)}")
        return []

async def process_user_request_with_county(user_data):
    """
    Procesa la solicitud del usuario con selección de condado y generación de application forms.
    
    Args:
        user_data: Diccionario con datos del usuario incluyendo county_selection
    
    Returns:
        Dict con resultados del procesamiento
    """
    try:
        logger.info(f"Procesando solicitud para {user_data.get('name', 'Usuario')}")
        logger.info(f"Condado seleccionado: {user_data.get('county_selection', 'no especificado')}")
        
        # Mapear selección de condado a configuración del scraper
        county_mapping = {
            "cork": {"county_id": "4", "name": "Cork"},
            "dublin": {"county_id": "27", "name": "Dublin"},
            "both": {"county_ids": ["4", "27"], "name": "Cork + Dublin"},
            "all": {"county_id": "", "name": "Toda Irlanda"}
        }
        
        county_selection = user_data.get('county_selection', 'all')
        county_config = county_mapping.get(county_selection, county_mapping['all'])
        
        # Si es "both" (Cork + Dublin), hacer scraping en ambos condados
        if county_selection == "both":
            logger.info("🌍 Haciendo scraping en Cork y Dublin")
            all_offers = []
            
            for county_id in county_config["county_ids"]:
                county_name = "Cork" if county_id == "4" else "Dublin"
                logger.info(f"📍 Scraping en {county_name}...")
                
                # Crear scraper con la misma configuración que el test
                scraper = EducationPosts(
                    level="primary",
                    county_id=county_id
                )
                
                # Hacer scraping
                county_offers = await scraper.fetch_all()
                
                # Agregar información del condado a cada oferta
                for offer in county_offers:
                    offer['scraped_county'] = county_name
                    offer['scraped_county_id'] = county_id
                
                all_offers.extend(county_offers)
                logger.info(f"✅ {county_name}: {len(county_offers)} ofertas encontradas")
                
                # Pausa entre condados para evitar sobrecarga
                await asyncio.sleep(10)
            
            offers = all_offers
            
        else:
            # Scraping en un solo condado o todos
            logger.info(f"📍 Haciendo scraping en: {county_config['name']}")
            
            # Crear scraper con la misma configuración que el test
            scraper = EducationPosts(
                level="primary",
                county_id=county_config.get("county_id", "")
            )
            
            offers = await scraper.fetch_all()
        
        if not offers:
            return {
                'success': False,
                'message': f'No se encontraron ofertas educativas en {county_config["name"]}'
            }
        
        logger.info(f"🎯 Total ofertas encontradas: {len(offers)}")
        
        # Filtrar ofertas que tengan email de contacto
        valid_offers = [offer for offer in offers if offer.get('email')]
        logger.info(f"📧 Ofertas con email válido: {len(valid_offers)}")
        
        if not valid_offers:
            return {
                'success': False,
                'message': f'No se encontraron ofertas con email de contacto en {county_config["name"]}'
            }
        
        # Verificar que el usuario ha enviado la plantilla PDF
        template_pdf = user_data.get('application_form')
        if not template_pdf or not os.path.exists(template_pdf) or not template_pdf.endswith('.pdf'):
            logger.error("❌ No se ha proporcionado una plantilla PDF válida por el usuario. Por favor, sube tu Application Form en PDF antes de continuar.")
            return {
                'success': False,
                'message': 'No se ha proporcionado una plantilla PDF válida. Sube tu Application Form en PDF antes de continuar.'
            }
        
        # Generar application forms PDFs usando la plantilla del usuario
        generated_forms = await generate_application_forms_from_offers(valid_offers, template_path=template_pdf)
        
        if not generated_forms:
            logger.error("❌ No se pudieron generar PDFs de application forms")
            return {
                'success': False,
                'message': 'No se pudieron generar PDFs de application forms. Verifica que la plantilla PDF sea válida.'
            }
        
        if len(generated_forms) != len(valid_offers):
            logger.warning(f"⚠️ Se generaron {len(generated_forms)} PDFs para {len(valid_offers)} ofertas")
            # Ajustar para usar solo las ofertas que tienen PDF correspondiente
            valid_offers = valid_offers[:len(generated_forms)]
        
        # Instanciar generador de emails y sender
        email_sender = EmailSender()
        ai_generator = AIEmailGeneratorV2()
        excel_profile = {}
        if user_data.get('excel_profile'):
            excel_profile = ai_generator.load_excel_profile(user_data['excel_profile'])
        errors = []
        run_id = uuid.uuid4().hex
        test_mode = bool(user_data.get('test_mode'))
        queue = ApplicationDeliveryQueue(
            policy=email_sender.send_policy,
            account_email=user_data.get('email', ''),
            run_id=run_id,
            test_mode=test_mode,
        )
        queue_items, enqueue_skipped_count = await queue.enqueue(valid_offers)

        if not queue_items:
            return {
                'success': True,
                'sent_count': 0,
                'total_offers': 0,
                'skipped_by_queue': enqueue_skipped_count,
                'message': 'No se añadieron ofertas nuevas a la cola; se conservaron los bloqueos de deduplicación.',
                'errors': errors,
            }

        # Test delivery uses the same local batch and spacing runner, but never
        # writes production queue metadata, quota, or reservations.
        if test_mode:
            test_recipient = os.getenv('EMAIL_ADDRESS')
            logger.info(
                "Encolando %s emails de prueba con lotes de %s y pausas de %s segundos.",
                len(queue_items),
                email_sender.send_policy.batch_limit,
                email_sender.send_policy.batch_pause_seconds,
            )

            async def send_test_queued_offer(offer):
                success = await email_sender.send_test_email(
                    test_recipient,
                    email_address=user_data.get('email'),
                    email_password=user_data.get('email_password'),
                    offer=offer,
                    run_id=run_id,
                    queue_managed=True,
                )
                if success:
                    logger.info("[TEST] Email de prueba enviado exitosamente.")
                else:
                    errors.append("[TEST] Error enviando email de prueba")
                return DeliveryAttempt(
                    success=success,
                    reason=email_sender._last_application_send_reason or "unknown",
                    error_category=email_sender._last_smtp_error_category,
                )

            queue_result = await queue.drain(queue_items, send_test_queued_offer)
            return {
                'success': True,
                'sent_count': queue_result.sent_count,
                'total_offers': queue_result.queued_count,
                'skipped_by_queue': queue_result.skipped_count + enqueue_skipped_count,
                'message': (
                    f'Se enviaron {queue_result.sent_count} emails de prueba de '
                    f'{queue_result.queued_count} encolados, con lotes y pausas locales.'
                ),
                'errors': errors,
            }

        forms_by_offer = {
            id(offer): form for offer, form in zip(valid_offers, generated_forms)
        }

        async def send_queued_offer(offer):
            form = forms_by_offer.get(id(offer), {})
            try:
                email_content = ai_generator.generate_email(
                    job_data=offer,
                    user_data=user_data,
                    excel_profile=excel_profile,
                )
                email_sent = await email_sender.send_application_email(
                    user_data=user_data,
                    offer=offer,
                    application_form_pdf=form.get('file_path'),
                    body=email_content,
                    run_id=run_id,
                    queue_managed=True,
                )
                if email_sent:
                    logger.info("Email enviado con application form adjunto.")
                else:
                    errors.append("Error enviando email para una oferta en cola")

                pdf_path = form.get('file_path')
                if pdf_path and os.path.exists(pdf_path):
                    os.remove(pdf_path)
                    logger.info("PDF temporal eliminado: %s", os.path.basename(pdf_path))
                return DeliveryAttempt(
                    success=email_sent,
                    reason=email_sender._last_application_send_reason or "unknown",
                    error_category=email_sender._last_smtp_error_category,
                )
            except Exception as exc:
                errors.append("Error preparando una oferta en cola")
                logger.error("Error preparando una oferta en cola (%s)", type(exc).__name__)
                return DeliveryAttempt(
                    success=False,
                    reason="preflight_unexpected_error",
                    error_category="preflight_unexpected_error",
                )

        queue_result = await queue.drain(queue_items, send_queued_offer)
        sent_count = queue_result.sent_count

        # Guardar resultados en archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        county_suffix = county_selection if county_selection != "all" else "ireland"
        filename = f"ofertas_{county_suffix}_{timestamp}.json"
        filepath = os.path.join("data", filename)
        
        # Crear directorio data si no existe
        os.makedirs("data", exist_ok=True)
        
        # Añadir información de PDFs generados al JSON
        result_data = {
            'offers': valid_offers,
            'generated_forms': generated_forms,
            'metadata': {
                'timestamp': timestamp,
                'county_searched': county_config["name"],
                'total_offers': len(valid_offers),
                'total_forms_generated': len(generated_forms)
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Resultados guardados en: {filepath}")
        
        return {
            'success': True,
            'sent_count': sent_count,
            'total_offers': len(valid_offers),
            'total_forms_generated': len(generated_forms),
            'county_searched': county_config["name"],
            'file_saved': filepath,
            'generated_forms': generated_forms,
            'errors': errors,
            'skipped_by_queue': queue_result.skipped_count + enqueue_skipped_count,
            'queue_deferred_daily_limit': queue_result.deferred_daily_limit,
            'message': f'Scraping completado exitosamente en {county_config["name"]}. Generados {len(generated_forms)} application forms PDFs y procesada la cola de envío.'
        }
        
    except Exception as e:
        logger.error(f"Error en proceso principal: {str(e)}")
        return {
            'success': False,
            'message': f'Error interno: {str(e)}'
        }

def main():
    """Función principal"""
    logger.info("🤖 Iniciando Bot de Telegram con selección de condados")
    
    # Verificar variables de entorno
    education_username = os.getenv('EDUCATIONPOSTS_USERNAME')
    education_password = os.getenv('EDUCATIONPOSTS_PASSWORD')
    if not education_username or not education_password:
        logger.error("❌ Credenciales de EducationPosts no están configuradas")
        logger.info("💡 Configura las credenciales en el archivo .env")
        return
    
    logger.info("✅ Variables de entorno configuradas correctamente")
    
    # Crear y iniciar bot
    try:
        # Configurar y ejecutar el bot
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not bot_token:
            logger.error("❌ No se encontró el token del bot de Telegram en las variables de entorno.")
            return
        
        bot = TelegramBot(token=bot_token)
        logger.info("🚀 Iniciando bot de Telegram...")
        
        # Configurar manejo de señales para cierre graceful
        def signal_handler(signum, frame):
            logger.info("⏹️ Señal de interrupción recibida, cerrando bot...")
            bot.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Iniciar bot
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error en el bot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("🔒 Cerrando bot...")
        try:
            bot.stop()
        except Exception as e:
            logger.error(f"Error al cerrar el bot: {e}")

if __name__ == "__main__":
    main()
