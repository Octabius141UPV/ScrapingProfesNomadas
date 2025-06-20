#!/usr/bin/env python3
"""
Scraping Profesores Nómadas
Punto de entrada principal del proyecto.
Este script ahora ejecuta la lógica de 'scrape_all_safe.py' que es la versión estable.
"""

import sys
import os
import asyncio

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        # Importamos la función 'main' del script estable y la ejecutamos
        from scripts.scrape_all_safe import main as scrape_main
        
        # El script original 'scrape_all_safe.py' maneja su propio bucle de eventos asyncio
        # por lo que simplemente llamamos a su función main.
        scrape_main()

    except ImportError:
        print("Error: No se pudo encontrar 'scrape_all_safe.py'.")
        print("Asegúrate de que el archivo existe en el directorio raíz del proyecto.")
        sys.exit(1)
    except Exception as e:
        print(f"Ocurrió un error inesperado durante la ejecución: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
