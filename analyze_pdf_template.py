#!/usr/bin/env python3
"""
Script para analizar el contenido del PDF plantilla y entender su estructura.
"""

import os
import sys
import pdfplumber

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.document_reader import DocumentReader
from utils.logger import setup_logger

def analyze_pdf_template():
    """Analiza el contenido del PDF plantilla"""
    
    logger = setup_logger()
    
    # Buscar el PDF plantilla
    template_path = "temp/application form álvaro.pdf"
    
    if not os.path.exists(template_path):
        logger.error(f"No se encontró el archivo: {template_path}")
        return
    
    logger.info(f"Analizando PDF: {template_path}")
    
    # Usar pdfplumber para analizar el contenido
    with pdfplumber.open(template_path) as pdf:
        logger.info(f"El PDF tiene {len(pdf.pages)} páginas")
        
        for page_num, page in enumerate(pdf.pages):
            logger.info(f"\n--- PÁGINA {page_num + 1} ---")
            
            # Extraer texto completo
            text = page.extract_text()
            logger.info(f"Texto completo de la página {page_num + 1}:")
            logger.info("=" * 50)
            logger.info(text)
            logger.info("=" * 50)
            
            # Extraer palabras con posiciones
            words = page.extract_words()
            logger.info(f"\nPalabras encontradas en página {page_num + 1}:")
            for i, word in enumerate(words[:20]):  # Mostrar solo las primeras 20
                logger.info(f"  {i+1}. '{word.get('text', '')}' en posición ({word.get('x0', 0):.1f}, {word.get('top', 0):.1f})")
            
            if len(words) > 20:
                logger.info(f"  ... y {len(words) - 20} palabras más")
            
            # Buscar campos específicos
            logger.info(f"\nBuscando campos específicos en página {page_num + 1}:")
            
            # Buscar POSITION ADVERTISED
            if 'POSITION ADVERTISED' in text:
                logger.info("✅ Encontrado: 'POSITION ADVERTISED'")
            else:
                logger.info("❌ No encontrado: 'POSITION ADVERTISED'")
            
            # Buscar School:
            if 'School:' in text:
                logger.info("✅ Encontrado: 'School:'")
            else:
                logger.info("❌ No encontrado: 'School:'")
            
            # Buscar ROLL NUMBER
            if 'ROLL NUMBER' in text:
                logger.info("✅ Encontrado: 'ROLL NUMBER'")
            else:
                logger.info("❌ No encontrado: 'ROLL NUMBER'")
            
            # Buscar otros campos comunes
            common_fields = ['Position', 'School', 'Roll', 'Number', 'Teacher', 'Application']
            for field in common_fields:
                if field in text:
                    logger.info(f"✅ Encontrado: '{field}'")
            
            # Mostrar líneas específicas que contengan palabras clave
            lines = text.split('\n')
            logger.info(f"\nLíneas que contienen palabras clave:")
            for i, line in enumerate(lines):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in ['position', 'school', 'roll', 'teacher', 'application']):
                    logger.info(f"  Línea {i+1}: '{line.strip()}'")

def test_document_reader():
    """Prueba el método _read_pdf del DocumentReader"""
    
    logger = setup_logger()
    doc_reader = DocumentReader()
    
    template_path = "temp/application form álvaro.pdf"
    
    if not os.path.exists(template_path):
        logger.error(f"No se encontró el archivo: {template_path}")
        return
    
    logger.info("Probando método _read_pdf del DocumentReader:")
    
    try:
        result = doc_reader._read_pdf(template_path)
        logger.info("Contenido extraído:")
        logger.info("=" * 50)
        logger.info(result.get('text', 'No se pudo extraer texto'))
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"Error leyendo PDF: {str(e)}")

if __name__ == "__main__":
    print("🔍 Analizando PDF plantilla...")
    
    print("\n1. Análisis con pdfplumber:")
    analyze_pdf_template()
    
    print("\n2. Análisis con DocumentReader:")
    test_document_reader()
    
    print("\n🎉 Análisis completado.") 