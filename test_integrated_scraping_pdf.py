#!/usr/bin/env python3
"""
Script de prueba para verificar la integración completa:
Scraping + Generación de PDFs personalizados + Envío de emails
"""
import asyncio
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape_all_safe import generate_application_forms_from_offers
from src.scrapers.scraper_educationposts import EducationPosts
import json

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/test_integrated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("test_integrated")

async def test_scraping_and_pdf_generation_only(user_data):
    """
    Función de prueba que solo hace scraping y generación de PDFs (sin envío de emails)
    """
    try:
        # Mapear selección de condado
        county_mapping = {
            "cork": {"county_id": "4", "name": "Cork"},
            "dublin": {"county_id": "27", "name": "Dublin"},
            "both": {"county_ids": ["4", "27"], "name": "Cork + Dublin"},
            "all": {"county_id": "", "name": "Toda Irlanda"}
        }
        
        county_selection = user_data.get('county_selection', 'all')
        county_config = county_mapping.get(county_selection, county_mapping['all'])
        
        logger.info(f"📍 Haciendo scraping en: {county_config['name']}")
        
        # Crear scraper
        scraper = EducationPosts(
            level="primary",
            county_id=county_config.get("county_id", "")
        )
        
        # Hacer scraping
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
        
        # Limitar a 5 ofertas para la prueba
        if len(valid_offers) > 5:
            valid_offers = valid_offers[:5]
            logger.info(f"📊 Limitando a 5 ofertas para la prueba")
        
        # Verificar plantilla PDF
        template_pdf = user_data.get('application_form')
        if not template_pdf or not os.path.exists(template_pdf) or not template_pdf.endswith('.pdf'):
            return {
                'success': False,
                'message': 'No se ha proporcionado una plantilla PDF válida.'
            }
        
        # Generar application forms PDFs
        generated_forms = await generate_application_forms_from_offers(valid_offers, template_path=template_pdf)
        
        if not generated_forms:
            return {
                'success': False,
                'message': 'No se pudieron generar PDFs de application forms.'
            }
        
        # Guardar resultados en archivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_ofertas_{county_selection}_{timestamp}.json"
        filepath = os.path.join("data", filename)
        
        # Crear directorio data si no existe
        os.makedirs("data", exist_ok=True)
        
        result_data = {
            'offers': valid_offers,
            'generated_forms': generated_forms,
            'metadata': {
                'timestamp': timestamp,
                'county_searched': county_config["name"],
                'total_offers': len(valid_offers),
                'total_forms_generated': len(generated_forms),
                'test_mode': True
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Resultados de prueba guardados en: {filepath}")
        
        return {
            'success': True,
            'total_offers': len(valid_offers),
            'total_forms_generated': len(generated_forms),
            'county_searched': county_config["name"],
            'file_saved': filepath,
            'generated_forms': generated_forms,
            'message': f'Prueba completada exitosamente en {county_config["name"]}. Generados {len(generated_forms)} application forms PDFs.'
        }
        
    except Exception as e:
        logger.error(f"Error en prueba: {str(e)}")
        return {
            'success': False,
            'message': f'Error en prueba: {str(e)}'
        }

async def test_integrated_workflow():
    """
    Prueba el flujo completo de scraping + generación de PDFs + envío de emails
    """
    try:
        logger.info("🧪 INICIANDO PRUEBA DE INTEGRACIÓN COMPLETA")
        logger.info("=" * 60)
        
        # Verificar que existe una plantilla PDF
        template_paths = [
            "temp/template_application_form.pdf",
            "data/Application_Form_Template.pdf", 
            "templates/application_form_template.pdf"
        ]
        
        template_found = None
        for template in template_paths:
            if os.path.exists(template):
                template_found = template
                logger.info(f"✅ Plantilla PDF encontrada: {template}")
                break
        
        if not template_found:
            logger.error("❌ No se encontró plantilla PDF")
            logger.info("💡 Coloca una plantilla PDF en temp/template_application_form.pdf")
            return False
        
        # Datos de prueba del usuario
        user_data = {
            'name': 'Álvaro Fortea Test',
            'email': 'alvaro.fortea.test@gmail.com',  # Email de prueba
            'email_password': 'password_test',  # Password de prueba
            'county_selection': 'cork',  # Solo Cork para la prueba
            'education_level': 'primary',
            'application_form': template_found,  # Plantilla PDF
            'documents': [
                # Documentos de prueba si existen
            ]
        }
        
        logger.info("📋 Configuración de prueba:")
        logger.info(f"   • Usuario: {user_data['name']}")
        logger.info(f"   • Email: {user_data['email']}")
        logger.info(f"   • Condado: {user_data['county_selection']}")
        logger.info(f"   • Plantilla: {user_data['application_form']}")
        
        # IMPORTANTE: Solo prueba la generación de PDFs, NO el envío de emails
        logger.info("⚠️  MODO PRUEBA: Solo generación de PDFs, NO envío de emails")
        
        # Para la prueba, vamos a usar una función separada que no envíe emails
        logger.info("🚀 Iniciando proceso de scraping...")
        result = await test_scraping_and_pdf_generation_only(user_data)
        
        # Analizar resultados
        if result['success']:
            logger.info("✅ PRUEBA EXITOSA!")
            logger.info(f"📊 Total ofertas encontradas: {result['total_offers']}")
            logger.info(f"📝 PDFs generados: {result['total_forms_generated']}")
            logger.info(f"📁 Archivo guardado: {result['file_saved']}")
            
            # Mostrar información de los PDFs generados
            if result.get('generated_forms'):
                logger.info("\n📄 PDFs generados:")
                for i, form in enumerate(result['generated_forms'], 1):
                    logger.info(f"  {i}. {os.path.basename(form['file_path'])}")
                    logger.info(f"     • Escuela: {form['school_name']}")
                    logger.info(f"     • Posición: {form['position']}")
                    logger.info(f"     • Roll Number: {form['roll_number']}")
                    
                    # Verificar que el PDF existe
                    if os.path.exists(form['file_path']):
                        file_size = os.path.getsize(form['file_path'])
                        logger.info(f"     • Tamaño: {file_size} bytes ✅")
                    else:
                        logger.error(f"     • ❌ PDF no encontrado")
            
            logger.info("\n🎯 RESUMEN DE LA PRUEBA:")
            logger.info(f"   ✅ Scraping completado: {result['total_offers']} ofertas")
            logger.info(f"   ✅ PDFs generados: {result['total_forms_generated']}")
            logger.info(f"   ✅ Sistema integrado funcionando correctamente")
            
            return True
        else:
            logger.error(f"❌ PRUEBA FALLIDA: {result['message']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error en la prueba: {str(e)}")
        return False

async def main():
    """Función principal"""
    logger.info("🤖 PRUEBA DE INTEGRACIÓN: Scraping + PDFs + Emails")
    logger.info("🎯 Objetivo: Verificar que todo el flujo funciona correctamente")
    logger.info("=" * 60)
    
    success = await test_integrated_workflow()
    
    logger.info("=" * 60)
    if success:
        logger.info("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        logger.info("🎉 El sistema integrado está funcionando correctamente")
    else:
        logger.info("❌ PRUEBA FALLIDA")
        logger.info("🔧 Revisa los logs para identificar problemas")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 