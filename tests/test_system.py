#!/usr/bin/env python3
import sys
import os

print("🧪 Test de verificación del sistema")
print("=" * 40)

try:
    # Test 1: Python
    print(f"✅ Python {sys.version}")
    
    # Test 2: Directorio actual  
    print(f"📁 Directorio: {os.getcwd()}")
    
    # Test 3: Variables de entorno
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        print(f"✅ Token configurado: {token[:10]}...")
    else:
        print("❌ Token no encontrado")
        
    # Test 4: Importar telegram
    try:
        import telegram
        print(f"✅ python-telegram-bot disponible")
    except ImportError as e:
        print(f"❌ Error importando telegram: {e}")
        
    # Test 5: Importar bot local
    try:
        from telegram_bot import TelegramBot
        bot = TelegramBot()
        print(f"✅ TelegramBot clase importada correctamente")
    except ImportError as e:
        print(f"❌ Error importando TelegramBot: {e}")
    except Exception as e:
        print(f"❌ Error creando TelegramBot: {e}")
        
except Exception as e:
    print(f"❌ Error general: {e}")

print("\n🏁 Test completado")
