#!/usr/bin/env python3
"""
Script de prueba para verificar el bot de Telegram con selección de condados.
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_environment():
    """Verifica que las variables de entorno estén configuradas"""
    print("🔍 Verificando configuración del entorno...\n")
    
    # Verificar token de Telegram
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if bot_token:
        print("✅ TELEGRAM_BOT_TOKEN configurado")
        print(f"   Token: {bot_token[:10]}...{bot_token[-5:]}")
    else:
        print("❌ TELEGRAM_BOT_TOKEN no configurado")
        return False
    
    # Verificar credenciales de EducationPosts
    username = os.getenv('EDUCATIONPOSTS_USERNAME')
    password = os.getenv('EDUCATIONPOSTS_PASSWORD')
    
    if username and password:
        print("✅ Credenciales de EducationPosts configuradas")
        print(f"   Usuario: {username}")
        print(f"   Password: {'*' * len(password)}")
    else:
        print("❌ Credenciales de EducationPosts no configuradas")
        return False
    
    print("\n🎉 ¡Configuración correcta! El bot está listo para funcionar.")
    return True

def show_usage():
    """Muestra instrucciones de uso"""
    print("""
📱 **Cómo usar el bot de Telegram:**

1. **Iniciar el bot:**
   python scrape_all_safe.py

2. **En Telegram:**
   - Busca tu bot usando el token configurado
   - Envía /start
   - Sigue las instrucciones paso a paso

3. **Flujo del bot:**
   📝 Nombre completo
   📧 Email de contacto  
   🔑 Contraseña de aplicación Gmail
   📎 Documentos (opcional)
   🗺️ Selección de condado (Cork/Dublin/Ambos/Toda Irlanda)
   ✅ Confirmación y procesamiento

4. **Resultado:**
   - Archivo JSON con todas las ofertas encontradas
   - Emails y requirements completos para cada oferta
   - Información de contacto de las escuelas

5. **Opciones de ubicación:**
   🏴󠁧󠁢󠁳󠁣󠁴󠁿 Cork - Condado de Cork
   🏢 Dublin - Área metropolitana de Dublin  
   🌍 Ambos - Cork + Dublin (recomendado)
   🇮🇪 Toda Irlanda - Todos los condados

💡 **Tip:** Seleccionar "Cork + Dublin" te dará las mejores oportunidades.
""")

if __name__ == "__main__":
    print("🤖 Test del Bot de Telegram - ScrapingProfesNomadas")
    print("=" * 50)
    
    if test_environment():
        show_usage()
        print("\n🚀 Para iniciar el bot, ejecuta:")
        print("   python scrape_all_safe.py")
    else:
        print("\n❌ Configura las variables de entorno primero:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - EDUCATIONPOSTS_USERNAME") 
        print("   - EDUCATIONPOSTS_PASSWORD")
        print("\nO crea un archivo .env con estas variables.")
