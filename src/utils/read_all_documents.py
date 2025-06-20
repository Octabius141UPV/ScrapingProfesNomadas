#!/usr/bin/env python3
"""
Script interactivo para leer y mostrar el contenido de múltiples documentos
"""

import os
import sys
import glob
from document_reader import DocumentReader

def get_documents_in_directory(directory: str) -> list:
    """
    Obtiene la lista de documentos soportados en un directorio
    
    Args:
        directory: Ruta al directorio a escanear
        
    Returns:
        Lista de rutas a documentos soportados
    """
    supported_extensions = ['.pdf', '.xlsx', '.xls', '.docx', '.doc']
    documents = []
    
    for ext in supported_extensions:
        pattern = os.path.join(directory, f'*{ext}')
        documents.extend(glob.glob(pattern))
    
    return sorted(documents)

def main():
    """Función principal"""
    print("📚 Lector de Documentos")
    print("=" * 50)
    
    # Obtener directorio actual
    current_dir = os.getcwd()
    
    # Obtener lista de documentos
    documents = get_documents_in_directory(current_dir)
    
    if not documents:
        print(f"❌ No se encontraron documentos en: {current_dir}")
        print("\n💡 Tipos de archivos soportados:")
        print("• PDF (.pdf)")
        print("• Excel (.xlsx, .xls)")
        print("• Word (.docx, .doc)")
        sys.exit(1)
    
    # Mostrar lista de documentos
    print("\n📋 Documentos encontrados:")
    for i, doc in enumerate(documents, 1):
        print(f"{i}. {os.path.basename(doc)}")
    
    # Crear lector de documentos
    reader = DocumentReader()
    
    while True:
        try:
            # Solicitar selección
            selection = input("\n📝 Selecciona un número (o 'q' para salir): ").strip()
            
            if selection.lower() == 'q':
                print("\n👋 ¡Hasta pronto!")
                break
            
            # Convertir selección a índice
            try:
                index = int(selection) - 1
                if 0 <= index < len(documents):
                    # Leer y mostrar documento
                    reader.print_document_content(documents[index])
                else:
                    print("❌ Número fuera de rango")
            except ValueError:
                print("❌ Por favor, ingresa un número válido")
                
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta pronto!")
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {str(e)}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Operación cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}") 