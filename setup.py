#!/usr/bin/env python3
"""
Script de instalación y configuración para ScrapingProfesNomadas
"""

import os
import sys
import subprocess
import shutil
from setuptools import setup, find_packages

def check_python_version():
    """Verificar que Python sea 3.8+"""
    if sys.version_info < (3, 8):
        print("❌ Error: Se requiere Python 3.8 o superior")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detectado")

def install_requirements():
    """Instalar dependencias de requirements.txt"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencias instaladas correctamente")
    except subprocess.CalledProcessError:
        print("❌ Error al instalar dependencias")
        sys.exit(1)

def setup_directories():
    """Crear directorios necesarios"""
    directories = ['logs', 'data', 'templates']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Directorio {directory}/ creado")

def setup_env_file():
    """Configurar archivo .env"""
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("✅ Archivo .env creado desde .env.example")
            print("⚠️  Recuerda configurar las variables en .env")
        else:
            print("❌ No se encontró .env.example")
    else:
        print("✅ Archivo .env ya existe")

def main():
    print("🚀 Configurando ScrapingProfesNomadas...")
    
    check_python_version()
    setup_directories()
    install_requirements()
    setup_env_file()
    
    # Configurar el paquete
    setup(
        name="scrapingprofesnomadas",
        version="0.1.0",
        packages=find_packages(),
        install_requires=[
            "python-telegram-bot>=20.0",
            "pandas>=1.5.0",
            "openpyxl>=3.0.0",
            "fpdf>=1.7.2",
        ],
        python_requires=">=3.8",
    )
    
    print("\n🎉 ¡Instalación completada!")
    print("📝 Próximos pasos:")
    print("   1. Configura las variables en .env")
    print("   2. Ejecuta: python run.py")

if __name__ == "__main__":
    main()
