#!/usr/bin/env python3
"""
Script para validar si un archivo Excel tiene la misma estructura que una plantilla de referencia
"""

import os
import sys
import argparse
from document_reader import DocumentReader

def main():
    parser = argparse.ArgumentParser(description='Valida la estructura de un archivo Excel respecto a una plantilla')
    parser.add_argument('file_path', help='Ruta al archivo Excel a validar')
    parser.add_argument('reference_path', help='Ruta al archivo Excel de referencia')
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"❌ El archivo a validar no existe: {args.file_path}")
        sys.exit(1)
    if not os.path.exists(args.reference_path):
        print(f"❌ El archivo de referencia no existe: {args.reference_path}")
        sys.exit(1)
    
    reader = DocumentReader()
    is_valid = reader.validate_excel_structure(args.file_path, args.reference_path)
    
    if is_valid:
        print(f"✅ La estructura de {os.path.basename(args.file_path)} es IGUAL a la plantilla {os.path.basename(args.reference_path)}")
    else:
        print(f"❌ La estructura de {os.path.basename(args.file_path)} NO coincide con la plantilla {os.path.basename(args.reference_path)}")

if __name__ == '__main__':
    main() 