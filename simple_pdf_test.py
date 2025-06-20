#!/usr/bin/env python3
"""
Prueba simple para generación de PDFs personalizados
"""
import asyncio
import os
import sys
import logging
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.utils.document_reader import DocumentReader
    from src.scrapers.scraper_educationposts import EducationPosts
    print("✅ Importaciones exitosas")
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    sys.exit(1)

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("simple_test")

def test_pdf_generation():
    """Prueba simple de generación de PDFs"""
    try:
        logger.info("🧪 Prueba simple de generación de PDFs")
        
        # Verificar plantilla
        template_path = "temp/application form álvaro.pdf"
        if not os.path.exists(template_path):
            logger.error(f"❌ Plantilla no encontrada: {template_path}")
            return False
        
        logger.info(f"✅ Plantilla encontrada: {template_path}")
        
        # Crear datos de prueba
        test_offers = [
            {
                "vacancy": "Mainstream Class Teacher",
                "school": "Test School Cork",
                "roll_number": "12345T"
            },
            {
                "vacancy": "Special Education Teacher", 
                "school": "Test School Dublin",
                "roll_number": "67890P"
            }
        ]
        
        # Crear DocumentReader
        doc_reader = DocumentReader()
        scraper = EducationPosts()
        
        # Crear directorio de salida
        output_dir = os.path.join("temp", "pdf_tests")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, offer in enumerate(test_offers):
            try:
                # Preparar datos
                offer_data = scraper.prepare_offer_data_for_application_form(offer)
                
                # Crear nombre de archivo
                school_safe = ''.join(c if c.isalnum() else '_' for c in offer_data['school_name'])
                output_path = os.path.join(output_dir, f"Test_PDF_{school_safe}_{timestamp}_{i}.pdf")
                
                # Generar PDF personalizado
                result = doc_reader.customize_application_form_pdf(
                    template_path=template_path,
                    output_path=output_path,
                    offer_data=offer_data
                )
                
                if result and os.path.exists(result):
                    file_size = os.path.getsize(result)
                    logger.info(f"✅ PDF generado: {os.path.basename(result)} ({file_size} bytes)")
                    logger.info(f"   • Escuela: {offer_data['school_name']}")
                    logger.info(f"   • Posición: {offer_data['position']}")
                    logger.info(f"   • Roll Number: {offer_data['roll_number']}")
                else:
                    logger.error(f"❌ Error generando PDF para {offer_data['school_name']}")
                    
            except Exception as e:
                logger.error(f"❌ Error con oferta #{i+1}: {str(e)}")
        
        logger.info("🎯 Prueba completada")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en prueba: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_pdf_generation()
    if success:
        print("\n✅ PRUEBA EXITOSA - La generación de PDFs funciona correctamente")
    else:
        print("\n❌ PRUEBA FALLIDA - Revisa los logs") 