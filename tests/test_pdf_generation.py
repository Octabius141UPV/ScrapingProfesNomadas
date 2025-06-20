#!/usr/bin/env python3
"""
Script de prueba para verificar la generación de PDFs personalizados
manteniendo la estructura original del PDF plantilla.
"""

import os
import sys
import json
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.document_reader import DocumentReader
from src.utils.logger import setup_logger

def test_pdf_generation():
    """Prueba la generación de PDFs personalizados"""
    
    # Configurar logger
    logger = setup_logger()
    
    # Crear instancia de DocumentReader
    doc_reader = DocumentReader()
    
    # Buscar un PDF de plantilla en temp/
    template_dir = "temp"
    template_pdf = None
    
    if os.path.exists(template_dir):
        for file in os.listdir(template_dir):
            if file.lower().endswith('.pdf') and 'application' in file.lower():
                template_pdf = os.path.join(template_dir, file)
                break
    
    if not template_pdf:
        logger.error("No se encontró un PDF de plantilla de Application Form en temp/")
        return False
    
    logger.info(f"Usando plantilla PDF: {template_pdf}")
    
    # Datos de prueba
    test_offer = {
        'position': 'Primary School Teacher',
        'school_name': 'St. Patrick\'s National School',
        'roll_number': '12345'
    }
    
    # Crear directorio de salida
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generar nombre de archivo de salida
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"test_application_form_{timestamp}.pdf"
    output_path = os.path.join(output_dir, output_filename)
    
    # Generar PDF personalizado
    logger.info("Generando PDF personalizado...")
    result = doc_reader.customize_application_form_pdf(
        template_path=template_pdf,
        output_path=output_path,
        offer_data=test_offer
    )
    
    if result:
        logger.info(f"✅ PDF generado exitosamente: {result}")
        
        # Verificar que el archivo existe
        if os.path.exists(result):
            file_size = os.path.getsize(result)
            logger.info(f"📄 Tamaño del archivo: {file_size} bytes")
            
            # Comparar con el original
            original_size = os.path.getsize(template_pdf)
            logger.info(f"📄 Tamaño del original: {original_size} bytes")
            
            return True
        else:
            logger.error("❌ El archivo generado no existe")
            return False
    else:
        logger.error("❌ Error generando PDF")
        return False

def test_with_real_data():
    """Prueba con datos reales de ofertas"""
    
    logger = setup_logger()
    doc_reader = DocumentReader()
    
    # Buscar archivos JSON de ofertas
    data_dir = "data"
    json_files = []
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.json') and 'ofertas' in file:
                json_files.append(os.path.join(data_dir, file))
    
    if not json_files:
        logger.error("No se encontraron archivos JSON de ofertas")
        return False
    
    # Usar el archivo más reciente
    latest_file = max(json_files, key=os.path.getctime)
    logger.info(f"Usando archivo de ofertas: {latest_file}")
    
    # Cargar ofertas
    with open(latest_file, 'r', encoding='utf-8') as f:
        offers = json.load(f)
    
    # Buscar plantilla PDF
    template_dir = "temp"
    template_pdf = None
    
    if os.path.exists(template_dir):
        for file in os.listdir(template_dir):
            if file.lower().endswith('.pdf') and 'application' in file.lower():
                template_pdf = os.path.join(template_dir, file)
                break
    
    if not template_pdf:
        logger.error("No se encontró plantilla PDF")
        return False
    
    # Crear directorio de salida
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Procesar las primeras 3 ofertas
    success_count = 0
    for i, offer in enumerate(offers[:3]):
        if 'position' in offer and 'school_name' in offer:
            logger.info(f"Procesando oferta {i+1}: {offer.get('position', 'N/A')}")
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"application_form_{i+1}_{timestamp}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            
            # Generar PDF
            result = doc_reader.customize_application_form_pdf(
                template_path=template_pdf,
                output_path=output_path,
                offer_data=offer
            )
            
            if result:
                success_count += 1
                logger.info(f"✅ PDF {i+1} generado: {result}")
            else:
                logger.error(f"❌ Error generando PDF {i+1}")
    
    logger.info(f"Resultado: {success_count}/{min(3, len(offers))} PDFs generados exitosamente")
    return success_count > 0

if __name__ == "__main__":
    print("🧪 Probando generación de PDFs personalizados...")
    
    # Prueba básica
    print("\n1. Prueba básica con datos de ejemplo:")
    if test_pdf_generation():
        print("✅ Prueba básica exitosa")
    else:
        print("❌ Prueba básica falló")
    
    # Prueba con datos reales
    print("\n2. Prueba con datos reales de ofertas:")
    if test_with_real_data():
        print("✅ Prueba con datos reales exitosa")
    else:
        print("❌ Prueba con datos reales falló")
    
    print("\n🎉 Pruebas completadas. Revisa la carpeta 'test_output' para ver los resultados.") 