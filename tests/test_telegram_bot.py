#!/usr/bin/env python3
"""
Script de prueba para verificar el bot de Telegram con selección de condados.
"""
import os
import sys
from dotenv import load_dotenv
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

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

class TestTelegramBotApplyLink(unittest.TestCase):
    def setUp(self):
        from src.bots.telegram_bot import TelegramBot, UserData
        self.TelegramBot = TelegramBot
        self.UserData = UserData
        self.bot = TelegramBot("dummy_token")
        # Simular usuario
        self.user = UserData()
        self.user.name = "Test User"
        self.user.email = "test@example.com"
        self.user.chat_id = 123456
        self.bot.user_data[1] = self.user

    def test_apply_link_offer(self):
        # Oferta con apply_link
        offer = {
            'school': 'Fake School',
            'vacancy': 'Teacher',
            'apply_link': 'https://www.educationposts.ie/post/apply/239126'
        }
        # Mock de send_message
        self.bot.application = MagicMock()
        self.bot.application.bot = MagicMock()
        self.bot.application.bot.send_message = AsyncMock()
        # Ejecutar
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.bot.send_application_email_for_offer(offer, self.user.email, "irrelevant")
        )
        # Debe devolver False (no se envía email)
        self.assertFalse(result)
        # Debe haberse llamado send_message con el enlace
        self.bot.application.bot.send_message.assert_awaited_with(
            chat_id=self.user.chat_id,
            text=unittest.mock.ANY
        )
        # El mensaje debe contener el enlace
        called_args = self.bot.application.bot.send_message.await_args.kwargs
        self.assertIn("apply manually", called_args['text'].lower() or "aplica manualmente" in called_args['text'].lower())
        self.assertIn(offer['apply_link'], called_args['text'])

if __name__ == "__main__":
    unittest.main()
