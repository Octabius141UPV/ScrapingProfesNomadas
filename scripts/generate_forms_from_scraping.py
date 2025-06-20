#!/usr/bin/env python3
"""
Script para generar application forms PDFs a partir de los resultados de scraping.
"""
import asyncio
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scrapers.scraper_educationposts import EducationPosts
from src.utils.document_reader import DocumentReader

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/generate_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("generate_forms")

async def generate_forms_from_json(json_file_path, template_path=None):
    """
    Genera application forms PDFs a partir de un archivo JSON de ofertas.
    
    Args:
        json_file_path: Ruta al archivo JSON con las ofertas
        template_path: Ruta a la plantilla PDF (opcional)
    """
    try:
        # Verificar que el archivo JSON existe
        if not os.path.exists(json_file_path):
            logger.error(f"❌ Archivo JSON no encontrado: {json_file_path}")
            return
        
        # Leer el archivo JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extraer ofertas (puede ser una lista directa o estar en una clave)
        if isinstance(data, list):
            offers = data
        elif isinstance(data, dict) and 'offers' in data:
            offers = data['offers']
        else:
            logger.error("❌ Formato de JSON no reconocido")
            return
        
        if not offers:
            logger.warning("❌ No hay ofertas en el archivo JSON")
            return
        
        logger.info(f"📄 Leyendo {len(offers)} ofertas desde: {json_file_path}")
        
        # Si no se proporciona plantilla, buscar una por defecto
        if not template_path:
            default_templates = [
                "data/Application_Form_Template.pdf",
                "temp/template_application_form.pdf",
                "templates/application_form_template.pdf"
            ]
            
            for template in default_templates:
                if os.path.exists(template):
                    template_path = template
                    logger.info(f"📋 Usando plantilla por defecto: {template_path}")
                    break
        
        if not template_path or not os.path.exists(template_path):
            logger.error("❌ No se encontró plantilla de application form")
            logger.info("💡 Coloca una plantilla PDF en data/Application_Form_Template.pdf")
            return
        
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
                # Preparar datos de la oferta
                offer_data = scraper.prepare_offer_data_for_application_form(offer)
                
                # Crear nombre para el archivo personalizado
                school_name_safe = ''.join(c if c.isalnum() else '_' for c in offer_data['school_name'])
                custom_filename = f"Application_Form_{school_name_safe}_{timestamp}_{i+1}.pdf"
                output_path = os.path.join(output_dir, custom_filename)
                
                # Generar PDF personalizado
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
                    logger.info(f"   📌 Escuela: {offer_data['school_name']}")
                    logger.info(f"   📌 Posición: {offer_data['position']}")
                    logger.info(f"   📌 Roll Number: {offer_data['roll_number']}")
                else:
                    logger.warning(f"⚠️ No se pudo generar PDF para: {offer_data['school_name']}")
                    
            except Exception as e:
                logger.error(f"❌ Error generando PDF #{i+1}: {str(e)}")
        
        logger.info(f"🎯 Total PDFs generados: {len(generated_forms)}")
        logger.info(f"📁 PDFs guardados en: {output_dir}")
        
        # Guardar resumen de PDFs generados
        summary_file = os.path.join(output_dir, f"summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_forms': generated_forms,
                'metadata': {
                    'timestamp': timestamp,
                    'source_file': json_file_path,
                    'template_used': template_path,
                    'total_offers': len(offers),
                    'total_forms_generated': len(generated_forms)
                }
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 Resumen guardado en: {summary_file}")
        
    except Exception as e:
        logger.error(f"❌ Error en generación de forms: {str(e)}")

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando generación de application forms PDFs...")
    
    # Obtener argumentos de línea de comandos
    if len(sys.argv) < 2:
        logger.error("❌ Uso: python generate_forms_from_scraping.py <archivo_json> [plantilla_pdf]")
        logger.info("💡 Ejemplo: python generate_forms_from_scraping.py data/ofertas_cork_20250618.json")
        return
    
    json_file = sys.argv[1]
    template_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Generar forms
    await generate_forms_from_json(json_file, template_file)
    
    logger.info("✅ Proceso completado")

if __name__ == "__main__":
    asyncio.run(main()) 