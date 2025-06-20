#!/usr/bin/env python3
"""
Script de verificación del proyecto ScrapingProfesNomadas
Verifica que la estructura y dependencias estén correctas
"""

import os
import sys
import importlib.util

def check_python_version():
    """Verificar versión de Python"""
    print("🐍 Verificando Python...")
    if sys.version_info >= (3, 8):
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} - OK")
        return True
    else:
        print(f"❌ Python {sys.version_info.major}.{sys.version_info.minor} - Requiere 3.8+")
        return False

def check_directories():
    """Verificar estructura de directorios"""
    print("\n📁 Verificando estructura...")
    required_dirs = ['src', 'data', 'logs', 'templates', 'tests', 'config']
    all_ok = True
    
    for directory in required_dirs:
        if os.path.exists(directory):
            print(f"✅ {directory}/")
        else:
            print(f"❌ {directory}/ - FALTANTE")
            all_ok = False
    
    return all_ok

def check_key_files():
    """Verificar archivos clave"""
    print("\n📄 Verificando archivos clave...")
    key_files = [
        'src/core/main.py',
        'src/bots/telegram_bot.py',
        'src/scrapers/scraper_educationposts.py',
        'src/generators/email_sender.py',
        'requirements.txt',
        'config.py',
        'run.py',
        'setup.py'
    ]
    
    all_ok = True
    for file_path in key_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - FALTANTE")
            all_ok = False
    
    return all_ok

def check_imports():
    """Verificar importaciones clave"""
    print("\n🔧 Verificando importaciones...")
    try:
        # Verificar importación principal
        sys.path.insert(0, os.getcwd())
        from src.core.main import main
        print("✅ Importación principal - OK")
        
        from config import validate_environment
        print("✅ Configuración - OK")
        
        return True
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        return False

def check_environment():
    """Verificar archivo .env"""
    print("\n⚙️ Verificando configuración...")
    if os.path.exists('.env'):
        print("✅ Archivo .env encontrado")
        return True
    elif os.path.exists('.env.example'):
        print("⚠️ Solo .env.example encontrado - Copia a .env y configura")
        return False
    else:
        print("❌ No se encontró .env ni .env.example")
        return False

def main():
    print("🎓 ScrapingProfesNomadas - Verificación del Sistema")
    print("=" * 60)
    
    checks = [
        ("Versión de Python", check_python_version),
        ("Estructura de directorios", check_directories),
        ("Archivos clave", check_key_files),
        ("Importaciones", check_imports),
        ("Configuración", check_environment)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        if check_func():
            passed += 1
    
    print(f"\n{'='*60}")
    if passed == total:
        print("🎉 ¡VERIFICACIÓN EXITOSA!")
        print("📋 El proyecto está listo para usar:")
        print("   1. Configura tu .env")
        print("   2. Instala dependencias: python setup.py")
        print("   3. Ejecuta: python run.py")
    else:
        print(f"⚠️ VERIFICACIÓN PARCIAL ({passed}/{total} OK)")
        print("🔧 Corrige los errores arriba antes de continuar")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
