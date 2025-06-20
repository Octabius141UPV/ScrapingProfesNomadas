#!/usr/bin/env python3
"""
Script para probar la generación automática de application forms
en el flujo normal del programa, después de obtener las ofertas.
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scrapers.scraper_educationposts import EducationPosts
from src.utils.document_reader import DocumentReader
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/test_application_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("app_form_test")

async def main():
    """
    Prueba la generación de application forms integrada en el flujo normal
    del programa, después de obtener las ofertas.
    """
    logger.info("🚀 Iniciando prueba de generación de application forms...")
    
    # Crear instancia del scraper 
    scraper = EducationPosts(
        level="primary",
        county_id="",  # Todos los condados
        max_workers=3,
        max_pages=1    # Solo una página para la prueba
    )
    
    try:
        # Obtener ofertas (limitar a una página)
        logger.info("🔍 Obteniendo ofertas de trabajo...")
        offers = await scraper.fetch_all(max_pages=1)
        
        logger.info(f"✅ Proceso completado. Se obtuvieron {len(offers)} ofertas")
        
        # Verificar que se generaron los application forms
        forms_count = sum(1 for offer in offers if 'custom_application_form' in offer)
        logger.info(f"� Se generaron {forms_count}/{min(10, len(offers))} application forms")
        
        # Mostrar rutas a los application forms
        if forms_count > 0:
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
            logger.info(f"📁 Los application forms se encuentran en: {temp_dir}")
            logger.info("📋 Lista de application forms generados:")
            
            for i, offer in enumerate([o for o in offers if 'custom_application_form' in o], 1):
                path = offer['custom_application_form']
                school = offer.get('school', 'N/A')
                vacancy = offer.get('vacancy', 'N/A')
                logger.info(f"{i}. {school} - {vacancy}: {os.path.basename(path)}")
        
        # Si no se generaron forms, mostrar advertencia
        else:
            logger.warning("⚠️ No se generó ningún application form. Verifica si hay ofertas disponibles.")
    
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
