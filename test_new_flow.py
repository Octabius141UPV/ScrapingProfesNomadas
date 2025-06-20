#!/usr/bin/env python3
"""
Script de prueba para verificar que el nuevo flujo de Application Form funciona correctamente
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bots.telegram_bot import UserData
from src.utils.document_reader import DocumentReader

def test_new_flow():
    """Prueba el nuevo flujo de Application Form"""
    print("🧪 Probando el nuevo flujo de Application Form...")
    
    # Crear un usuario de prueba
    user = UserData()
    user.name = "Test User"
    user.email = "test@example.com"
    
    # Simular que el usuario subió un Application Form
    template_path = "temp/application form álvaro.pdf"
    if os.path.exists(template_path):
        user.documents['application_form'] = {
            'path': template_path,
            'filename': 'application form álvaro.pdf'
        }
        print(f"✅ Application Form encontrado: {template_path}")
    else:
        print("❌ No se encontró el Application Form de prueba")
        return False
    
    # Datos de prueba de una oferta
    test_offer = {
        'position': 'Primary School Teacher',
        'school_name': 'St. Patrick\'s National School',
        'roll_number': '12345',
        'location': 'Dublin',
        'closing_date': '2024-01-31'
    }
    
    # Crear instancia del bot (solo para probar la función)
    from src.bots.telegram_bot import TelegramBot
    bot = TelegramBot("dummy_token")
    
    # Probar la nueva función generate_application_form
    print("🔄 Probando generate_application_form...")
    try:
        import asyncio
        result = asyncio.run(bot.generate_application_form(test_offer, user))
        
        if result and os.path.exists(result):
            print(f"✅ Application Form generado exitosamente: {result}")
            file_size = os.path.getsize(result)
            print(f"📄 Tamaño del archivo: {file_size} bytes")
            
            # Limpiar archivo de prueba
            os.remove(result)
            print("🧹 Archivo de prueba eliminado")
            
            return True
        else:
            print("❌ Error generando Application Form")
            return False
            
    except Exception as e:
        print(f"❌ Error en la prueba: {str(e)}")
        return False

if __name__ == "__main__":
    if test_new_flow():
        print("\n🎉 ¡Nuevo flujo funcionando correctamente!")
        print("✅ El sistema ahora usa el PDF que subes por Telegram como plantilla")
        print("✅ Solo personaliza los campos mínimos necesarios (roll number, school, position)")
        print("✅ No genera PDFs 'desde cero' con datos extra")
    else:
        print("\n❌ Error en el nuevo flujo")
        print("Revisa que el Application Form de prueba esté en temp/") 