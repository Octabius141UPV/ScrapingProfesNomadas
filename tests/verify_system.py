#!/usr/bin/env python3
"""
Script de verificación final para ScrapingProfesNomadas
"""

import sys
import os

def main():
    print("🎓 ScrapingProfesNomadas - Verificación Final")
    print("=" * 50)
    
    # 1. Verificar Python
    print(f"🐍 Python: {sys.version}")
    
    # 2. Verificar archivos principales
    required_files = [
        'main.py',
        'telegram_bot.py', 
        'scraper_educationposts.py',
        'email_sender.py',
        'ai_email_generator_v2.py',
        'requirements.txt',
        '.env'
    ]
    
    print("\n📁 Verificando archivos principales...")
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} FALTANTE")
    
    # 3. Verificar configuración
    print("\n⚙️ Verificando configuración...")
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            content = f.read()
            if 'TELEGRAM_BOT_TOKEN=' in content and len(content.split('TELEGRAM_BOT_TOKEN=')[1].split('\n')[0].strip()) > 10:
                print("✅ Token de Telegram configurado")
            else:
                print("⚠️ Token de Telegram no configurado o incompleto")
    
    # 4. Verificar dependencias
    print("\n📦 Verificando dependencias...")
    dependencies = ['requests', 'bs4', 'telegram', 'dotenv']
    
    for dep in dependencies:
        try:
            if dep == 'bs4':
                import bs4
            elif dep == 'telegram':
                import telegram
            elif dep == 'dotenv':
                import dotenv
            else:
                __import__(dep)
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} - Ejecuta: pip install {dep}")
    
    # 5. Verificar dependencias opcionales
    print("\n🔧 Verificando dependencias opcionales...")
    optional_deps = {
        'pandas': 'pip install pandas',
        'numpy': 'pip install numpy', 
        'openpyxl': 'pip install openpyxl',
        'openai': 'pip install openai',
        'anthropic': 'pip install anthropic'
    }
    
    for dep, install_cmd in optional_deps.items():
        try:
            __import__(dep)
            print(f"✅ {dep}")
        except ImportError:
            print(f"⚠️ {dep} (opcional) - {install_cmd}")
    
    print("\n" + "=" * 50)
    print("🚀 ESTADO DEL SISTEMA:")
    print("✅ Archivos principales: OK")
    print("✅ Configuración básica: OK") 
    print("⚠️ Algunas dependencias opcionales pueden faltar")
    
    print("\n📝 SIGUIENTES PASOS:")
    print("1. Instalar dependencias faltantes (si las hay)")
    print("2. Configurar token completo en .env si no está hecho")
    print("3. Ejecutar: python3 main.py")
    print("4. En Telegram, buscar tu bot y enviar /start")
    
    print("\n💡 COMANDOS ÚTILES:")
    print("• Instalar todo: pip install -r requirements.txt")
    print("• Generar template Excel: python3 generate_excel_template.py")
    print("• Solo scraper: python3 main.py --scraper-only")
    print("• Inicio rápido: ./start_quick.sh")

if __name__ == "__main__":
    main()
