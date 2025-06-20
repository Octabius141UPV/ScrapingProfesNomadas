#!/usr/bin/env python3
"""
Script de ejemplo para ejecutar scraping y generación de application forms PDFs de forma integrada.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrape_all_safe import process_user_request_with_county

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s"
)
logger = logging.getLogger("run_scraping_with_forms")

async def run_scraping_and_forms():
    """Ejecuta scraping y generación de forms de forma integrada"""
    try:
        logger.info("🚀 Iniciando scraping y generación de application forms PDFs...")
        
        # Configurar datos de usuario (puedes modificar estos valores)
        user_data = {
            'name': 'Usuario Ejemplo',
            'county_selection': 'cork',  # 'cork', 'dublin', 'both', 'all'
            'education_level': 'primary'
        }
        
        logger.info(f"📍 Condado seleccionado: {user_data['county_selection']}")
        logger.info(f"📚 Nivel educativo: {user_data['education_level']}")
        
        # Ejecutar scraping y generación de forms
        result = await process_user_request_with_county(user_data)
        
        if result['success']:
            logger.info("✅ Proceso completado exitosamente!")
            logger.info(f"📊 Total ofertas encontradas: {result['total_offers']}")
            logger.info(f"📝 PDFs generados: {result['total_forms_generated']}")
            logger.info(f"📁 Archivo guardado: {result['file_saved']}")
            logger.info(f"📋 Mensaje: {result['message']}")
            
            # Mostrar información de los PDFs generados
            if result.get('generated_forms'):
                logger.info("\n📄 PDFs generados:")
                for i, form in enumerate(result['generated_forms'], 1):
                    logger.info(f"  {i}. {os.path.basename(form['file_path'])}")
                    logger.info(f"     Escuela: {form['school_name']}")
                    logger.info(f"     Posición: {form['position']}")
                    logger.info(f"     Roll Number: {form['roll_number']}")
        else:
            logger.error(f"❌ Error en el proceso: {result['message']}")
            
    except Exception as e:
        logger.error(f"❌ Error inesperado: {str(e)}")

async def main():
    """Función principal"""
    logger.info("🤖 Sistema de Scraping + Generación de Application Forms PDFs")
    logger.info("=" * 60)
    
    # Verificar que existe una plantilla
    template_paths = [
        "data/Application_Form_Template.pdf",
        "temp/template_application_form.pdf",
        "templates/application_form_template.pdf"
    ]
    
    template_found = False
    for template in template_paths:
        if os.path.exists(template):
            logger.info(f"✅ Plantilla encontrada: {template}")
            template_found = True
            break
    
    if not template_found:
        logger.warning("⚠️ No se encontró plantilla de application form")
        logger.info("💡 Coloca una plantilla PDF en data/Application_Form_Template.pdf")
        logger.info("💡 O ejecuta el bot de Telegram para descargar la plantilla")
    
    # Ejecutar el proceso
    await run_scraping_and_forms()
    
    logger.info("=" * 60)
    logger.info("✅ Proceso completado")

if __name__ == "__main__":
    asyncio.run(main()) 