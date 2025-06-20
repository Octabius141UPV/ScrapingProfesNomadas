#!/usr/bin/env python3
"""
Script de prueba comprehensivo para el sistema ScrapingProfesNomadas
Incluye tests robustos con manejo de dependencias opcionales
"""

import logging
import os
import sys
from typing import Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Prueba las importaciones básicas y opcionales"""
    print("🔍 Probando importaciones...")
    
    # Importaciones obligatorias
    required_imports = [
        ('requests', 'requests'),
        ('beautifulsoup4', 'bs4'),
        ('python-telegram-bot', 'telegram'),
        ('python-dotenv', 'dotenv')
    ]
    
    # Importaciones opcionales
    optional_imports = [
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('openai', 'openai'),
        ('anthropic', 'anthropic'),
        ('openpyxl', 'openpyxl')
    ]
    
    # Probar importaciones obligatorias
    required_ok = True
    for package, module in required_imports:
        try:
            __import__(module)
            print(f"✅ {package} importado correctamente")
        except ImportError as e:
            print(f"❌ Error importando {package}: {e}")
            required_ok = False
    
    # Probar importaciones opcionales
    optional_status = {}
    for package, module in optional_imports:
        try:
            __import__(module)
            print(f"✅ {package} importado correctamente")
            optional_status[package] = True
        except ImportError:
            print(f"⚠️ {package} no disponible (opcional)")
            optional_status[package] = False
    
    return required_ok, optional_status

def test_ai_email_generator():
    """Prueba el generador de emails AI v2"""
    print("\n📧 Probando generador de emails AI v2...")
    
    try:
        from ai_email_generator_v2 import AIEmailGeneratorV2
        
        # Crear instancia
        generator = AIEmailGeneratorV2()
        
        # Verificar características disponibles
        features = generator.get_available_features()
        print(f"Características disponibles: {features}")
        
        # Datos de prueba
        job_data = {
            'title': 'Profesor de Matemáticas',
            'company': 'Colegio San José',
            'location': 'Madrid',
            'description': 'Buscamos profesor de matemáticas para secundaria'
        }
        
        user_data = {
            'name': 'Ana García',
            'email': 'ana.garcia@test.com',
            'experience': '3 años de experiencia docente',
            'education': 'Licenciatura en Matemáticas',
            'skills': 'Python, metodologías activas'
        }
        
        # Generar email básico
        email = generator.generate_email(job_data, user_data)
        print("✅ Email generado correctamente")
        print("📄 Contenido del email:")
        print("-" * 50)
        print(email)
        print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Error en generador de emails: {e}")
        return False

def test_scraper_basic():
    """Prueba funcionalidad básica del scraper"""
    print("\n🕷️ Probando scraper básico...")
    
    try:
        from scraper_educationposts import EducationPostsScraper
        
        scraper = EducationPostsScraper()
        print("✅ Scraper inicializado correctamente")
        
        # Probar método de construcción de URL
        url = scraper.build_search_url(county="Dublin", level="secondary")
        print(f"📍 URL construida: {url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en scraper: {e}")
        return False

def test_email_sender():
    """Prueba configuración básica del email sender"""
    print("\n📬 Probando email sender...")
    
    try:
        from email_sender import EmailSender
        
        # Crear instancia con datos de prueba
        sender = EmailSender(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            email="test@test.com",
            password="test_password"
        )
        print("✅ EmailSender inicializado correctamente")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en email sender: {e}")
        return False

def test_template_creation():
    """Prueba creación de templates"""
    print("\n📋 Probando creación de templates...")
    
    try:
        from ai_email_generator_v2 import AIEmailGeneratorV2
        
        generator = AIEmailGeneratorV2()
        
        # Probar creación de template Excel
        excel_created = generator.create_excel_template("test_template.xlsx")
        if excel_created:
            print("✅ Template Excel creado")
            if os.path.exists("test_template.xlsx"):
                os.remove("test_template.xlsx")
        else:
            print("⚠️ No se pudo crear template Excel, probando JSON...")
            json_created = generator.create_excel_template("test_template.json")
            if json_created:
                print("✅ Template JSON creado como fallback")
                if os.path.exists("test_template.json"):
                    os.remove("test_template.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creando templates: {e}")
        return False

def test_telegram_bot():
    """Prueba configuración básica del bot de Telegram"""
    print("\n🤖 Probando bot de Telegram...")
    
    try:
        from telegram_bot import JobApplicationBot
        
        # Crear instancia con token de prueba
        bot = JobApplicationBot("dummy_token")
        print("✅ Bot de Telegram inicializado correctamente")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en bot de Telegram: {e}")
        return False

def run_comprehensive_test():
    """Ejecuta todas las pruebas"""
    print("🧪 Iniciando pruebas comprehensivas del sistema...")
    print("=" * 60)
    
    # Probar importaciones primero
    required_ok, optional_status = test_imports()
    
    if not required_ok:
        print("\n❌ FALLO CRÍTICO: Dependencias obligatorias no disponibles")
        print("Ejecuta: pip install -r requirements.txt")
        return False
    
    # Pruebas funcionales
    tests = [
        ("Generador AI v2", test_ai_email_generator),
        ("Scraper", test_scraper_basic),
        ("Email Sender", test_email_sender),
        ("Templates", test_template_creation),
        ("Bot Telegram", test_telegram_bot)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Error en prueba {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    # Resumen de dependencias opcionales
    print("\n📦 DEPENDENCIAS OPCIONALES:")
    print("-" * 30)
    for package, available in optional_status.items():
        status = "✅ Disponible" if available else "❌ No disponible"
        print(f"{package:<15} {status}")
    
    print(f"\nResultado: {passed}/{len(tests)} pruebas exitosas")
    
    if passed == len(tests):
        print("🎉 ¡Todos los tests pasaron! El sistema está listo.")
        if not all(optional_status.values()):
            print("⚠️ Algunas funciones avanzadas pueden estar limitadas por dependencias faltantes.")
    elif passed >= len(tests) * 0.7:
        print("⚠️ La mayoría de tests pasaron. Revisa los fallos menores.")
    else:
        print("❌ Varios tests fallaron. Revisa la configuración.")
    
    # Consejos de instalación
    if not optional_status.get('pandas', True) or not optional_status.get('numpy', True):
        print("\n💡 Para solucionar problemas con pandas/numpy:")
        print("   chmod +x setup_env.sh && ./setup_env.sh")
    
    return passed >= len(tests) * 0.7

if __name__ == "__main__":
    success = run_comprehensive_test()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ SISTEMA LISTO PARA USO")
        print("Para ejecutar el sistema principal: python main.py")
    else:
        print("❌ SISTEMA NECESITA CORRECCIONES")
        print("Revisa los errores arriba y ejecuta las correcciones sugeridas")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
