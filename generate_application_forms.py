#!/usr/bin/env python3
"""
Script para scrapear ofertas de trabajo y generar application forms personalizados.
"""
import asyncio
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import tempfile
from src.utils.document_reader import DocumentReader

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
load_dotenv()

from src.scrapers.scraper_educationposts import EducationPosts

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/application_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("application_forms")

async def main():
    """Función principal para scrapear y generar application forms"""
    logger.info("🚀 Iniciando proceso de scraping y generación de application forms...")
    
    # Path a la plantilla de application form
    template_path = input("🖊️ Ingresa la ruta a tu plantilla de application form (.pdf): ").strip()
    
    if not os.path.exists(template_path) or not template_path.lower().endswith('.pdf'):
        logger.error(f"❌ Error: El archivo de plantilla no existe o no es un .pdf: {template_path}")
        return
    
    # Configurar y ejecutar el scraper
    logger.info("🕷️ Iniciando scraping de ofertas de trabajo...")
    
    try:
        scraper = EducationPosts(
            level="primary",
            # Puedes configurar más parámetros según necesites
            max_pages=1  # Solo para obtener un número limitado de ofertas
        )
        
        # Obtener ofertas
        ofertas = await scraper.fetch_all(max_pages=1)
        
        if not ofertas:
            logger.error("❌ No se encontraron ofertas")
            return
        
        logger.info(f"✅ Se encontraron {len(ofertas)} ofertas")
        
        # Limitar a 10 ofertas para la prueba
        if len(ofertas) > 10:
            ofertas = ofertas[:10]
            logger.info(f"📊 Limitando a 10 ofertas para la prueba")
        
        # Crear directorio para los application forms personalizados
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'application_forms')
        os.makedirs(output_dir, exist_ok=True)
        
        # Procesar cada oferta y generar un application form personalizado
        logger.info("📝 Generando application forms personalizados...")
        document_reader = DocumentReader()
        
        for i, oferta in enumerate(ofertas):
            # Preparar los datos para el application form
            offer_data = scraper.prepare_offer_data_for_application_form(oferta)
            
            # Crear nombre para el archivo personalizado
            school_name_safe = ''.join(c if c.isalnum() else '_' for c in offer_data['school_name'])
            custom_filename = f"Application_Form_{school_name_safe}_{i+1}.pdf"
            output_path = os.path.join(output_dir, custom_filename)
            
            # Personalizar el documento PDF
            try:
                personalized_path = document_reader.customize_application_form_pdf(
                    template_path=template_path,
                    output_path=output_path,
                    offer_data=offer_data
                )
                
                if personalized_path:
                    logger.info(f"✅ [{i+1}/{len(ofertas)}] Application form personalizado: {personalized_path}")
                    logger.info(f"   📌 Posición: {offer_data['position']}")
                    logger.info(f"   📌 Escuela: {offer_data['school_name']}")
                    logger.info(f"   📌 Roll Number: {offer_data['roll_number']}")
                else:
                    logger.warning(f"⚠️ No se pudo personalizar el application form para: {offer_data['school_name']}")
                    
            except Exception as e:
                logger.error(f"❌ Error al personalizar application form #{i+1}: {str(e)}")
        
        logger.info(f"✅ Todos los application forms han sido generados en: {output_dir}")
        
    except Exception as e:
        logger.error(f"❌ Error durante el proceso: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
