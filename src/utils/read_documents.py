#!/usr/bin/env python3
"""
Script para leer y mostrar el contenido de documentos
"""

import os
import sys
import argparse
from document_reader import DocumentReader

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Lee y muestra el contenido de documentos')
    parser.add_argument('file_path', help='Ruta al archivo a leer')
    args = parser.parse_args()
    
    # Verificar que el archivo existe
    if not os.path.exists(args.file_path):
        print(f"❌ Error: El archivo {args.file_path} no existe")
        sys.exit(1)
    
    # Crear lector de documentos
    reader = DocumentReader()
    
    # Leer y mostrar contenido
    reader.print_document_content(args.file_path)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Operación cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}") 