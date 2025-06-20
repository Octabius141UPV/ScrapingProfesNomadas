#!/usr/bin/env python3
"""
Script de prueba para verificar la generación de application forms PDF.
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.document_reader import DocumentReader

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s"
)
logger = logging.getLogger("test_pdf_forms")

def test_pdf_generation():
    """Prueba la generación de application forms PDF"""
    logger.info("🧪 Iniciando prueba de generación de PDFs...")
    
    # Datos de prueba
    test_offer_data = {
        'position': 'Primary School Teacher',
        'school_name': 'St. Patrick\'s National School',
        'roll_number': '12345'
    }
    
    # Path a la plantilla PDF (deberás proporcionar una)
    template_path = input("🖊️ Ingresa la ruta a tu plantilla PDF de prueba: ").strip()
    
    if not os.path.exists(template_path):
        logger.error(f"❌ Plantilla no encontrada: {template_path}")
        return
    
    # Crear directorio de salida
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    # Crear nombre para el archivo de prueba
    output_path = os.path.join(output_dir, f"test_application_form_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    
    # Inicializar DocumentReader
    document_reader = DocumentReader()
    
    try:
        # Generar el PDF personalizado
        logger.info("📝 Generando PDF de prueba...")
        result_path = document_reader.customize_application_form_pdf(
            template_path=template_path,
            output_path=output_path,
            offer_data=test_offer_data
        )
        
        if result_path:
            logger.info(f"✅ PDF generado exitosamente: {result_path}")
            logger.info(f"📌 Datos utilizados:")
            logger.info(f"   - Position: {test_offer_data['position']}")
            logger.info(f"   - School: {test_offer_data['school_name']}")
            logger.info(f"   - Roll Number: {test_offer_data['roll_number']}")
        else:
            logger.error("❌ No se pudo generar el PDF")
            
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {str(e)}")

if __name__ == "__main__":
    test_pdf_generation() 