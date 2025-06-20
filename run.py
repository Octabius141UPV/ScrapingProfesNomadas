#!/usr/bin/env python3
"""
Scraping Profesores Nómadas
Punto de entrada principal del proyecto
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from src.core.main import main
    main()
