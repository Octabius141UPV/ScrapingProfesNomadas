#!/usr/bin/env python3
"""
Scraping Profesores Nómadas
Punto de entrada principal del proyecto.
Este script ahora ejecuta la lógica de 'scrape_all_safe.py' que es la versión estable.
"""

import sys
import os
import asyncio
import traceback

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


SCRAPER_ENTRYPOINT_MODULE = "scripts.scrape_all_safe"


def _load_scrape_main():
    """Load the stable scraper entry point without masking its dependencies."""
    from scripts.scrape_all_safe import main as scrape_main

    return scrape_main


def main():
    """Run the stable scraper and return a process exit code."""
    try:
        scrape_main = _load_scrape_main()
    except ModuleNotFoundError as error:
        if error.name != SCRAPER_ENTRYPOINT_MODULE:
            raise

        print("Error: No se pudo encontrar 'scrape_all_safe.py'.")
        print("Asegúrate de que el archivo existe en el directorio raíz del proyecto.")
        return 1

    # El script original 'scrape_all_safe.py' maneja su propio bucle de eventos asyncio
    # por lo que simplemente llamamos a su función main.
    scrape_main()
    return 0


def run():
    """Run the entry point while preserving unexpected import diagnostics."""
    try:
        return main()
    except Exception as e:
        print(f"Ocurrió un error inesperado durante la ejecución: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run())
