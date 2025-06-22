#!/usr/bin/env python3
"""
Script de ejemplo para ejecutar scraping y generación de application forms PDFs de forma integrada.
"""
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
            'education_level': 'primary',
            # Asegúrate de que la plantilla existe o el bot te la pedirá.
            # Ejemplo de cómo podría pasarse una plantilla si el bot no gestionara la subida:
            'application_form': 'data/Application Form Álvaro.pdf'
        }
        
        logger.info(f"📍 Condado seleccionado: {user_data['county_selection']}")
        logger.info(f"📚 Nivel educativo: {user_data['education_level']}")
        
        # Ejecutar scraping y generación de forms
        result = await process_user_request_with_county(user_data)
        
        if result.get('success'):
            logger.info("✅ Proceso completado exitosamente!")
            if 'total_offers' in result:
                logger.info(f"📊 Total ofertas encontradas: {result['total_offers']}")
            if 'total_forms_generated' in result:
                logger.info(f"📝 PDFs generados: {result['total_forms_generated']}")
            if result.get('file_saved'):
                logger.info(f"📁 Archivo guardado: {result['file_saved']}")
            logger.info(f"📋 Mensaje: {result['message']}")
            
            # Mostrar información de los PDFs generados
            if result.get('generated_forms'):
                logger.info("\n📄 PDFs generados:")
                for i, form in enumerate(result['generated_forms'], 1):
                    logger.info(f"  {i}. {os.path.basename(form['file_path'])}")
                    logger.info(f"     Escuela: {form.get('school_name', 'N/A')}")
                    logger.info(f"     Posición: {form.get('position', 'N/A')}")
                    if form.get('roll_number'):
                        logger.info(f"     Roll Number: {form['roll_number']}")
        else:
            logger.error(f"❌ Error en el proceso: {result.get('message', 'Error desconocido')}")
            
    except Exception as e:
        logger.error(f"❌ Error inesperado: {str(e)}", exc_info=True)

async def main():
    """Función principal"""
    logger.info("🤖 Sistema de Scraping + Generación de Application Forms PDFs")
    logger.info("=" * 60)
    
    # Este script asume que la plantilla será gestionada por el bot o
    # que la ruta se provee en `user_data`.
    # Puedes añadir una verificación aquí si lo necesitas.
    
    # Ejecutar el proceso
    await run_scraping_and_forms()
    
    logger.info("=" * 60)
    logger.info("✅ Proceso completado")

if __name__ == "__main__":
    asyncio.run(main()) 