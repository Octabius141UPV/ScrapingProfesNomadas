#!/usr/bin/env python3
"""
Script temporal para leer los archivos de ejemplo
"""

import os
from document_reader import DocumentReader

def main():
    """Función principal"""
    reader = DocumentReader()
    
    # Leer archivos de ejemplo
    example_files = [
        'data/practicasPlantilla.xlsx',
        'data/Contactos de Referentes.xlsx'
    ]
    
    for file_path in example_files:
        if os.path.exists(file_path):
            print(f"\n📄 Leyendo: {file_path}")
            reader.print_document_content(file_path)
        else:
            print(f"❌ Archivo no encontrado: {file_path}")

if __name__ == '__main__':
    main() 