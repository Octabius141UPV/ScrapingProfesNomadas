#!/usr/bin/env python3
"""
Test para verificar que se maneja correctamente el caso donde user.documents contiene diccionarios.
"""

import asyncio
import json
import os
import sys
from unittest.mock import Mock, AsyncMock

# Añadir el directorio src al path
sys.path.append('src')

from src.bots.telegram_bot import TelegramBot, UserData

async def test_dict_error_fix():
    """Test que verifica que se maneja correctamente user.documents con diccionarios"""
    
    # Crear una instancia del bot
    bot = TelegramBot("test_token")
    
    # Crear un usuario de prueba con documentos (algunos como diccionarios)
    user = UserData()
    user.name = "Test User"
    user.email = "test@example.com"
    user.documents = {
        'application_form': 'temp/test_application_form.pdf',
        'cv': {'path': 'temp/test_cv.pdf', 'type': 'pdf'},  # Diccionario
        'letter_of_application': 'temp/test_letter.pdf',
        'degree': {'path': 'temp/test_degree.pdf'},  # Diccionario
        'tc_registration': 'temp/test_tc.pdf',
        'religion_certificate': 'temp/test_religion.pdf',
        'practicas': 'temp/test_practicas.xlsx',
        'referentes': 'temp/test_referentes.xlsx'
    }
    
    # Crear archivos temporales de prueba
    os.makedirs('temp', exist_ok=True)
    for doc_key, doc_path in user.documents.items():
        if isinstance(doc_path, dict):
            actual_path = doc_path['path']
        else:
            actual_path = doc_path
        with open(actual_path, 'w') as f:
            f.write("test content")
    
    # Caso de prueba: oferta que requiere documentos mixtos
    offer = {
        'school_name': 'Test School',
        'position': 'Primary Teacher',
        'email': 'test@school.ie',
        'url': 'https://example.com',
        'required_documents': [
            'Application Form',
            'CV',
            'Letter of Application',
            'Degree'
        ]
    }
    
    print("🧪 Test de manejo de diccionarios en user.documents...")
    print(f"🏫 Escuela: {offer['school_name']}")
    print(f"📝 Posición: {offer['position']}")
    print(f"📄 Documentos requeridos: {offer['required_documents']}")
    
    # Simular el Application Form personalizado
    customized_paths = {'application_form': 'temp/test_application_form.pdf'}
    
    try:
        # Obtener adjuntos requeridos
        required_attachments = bot.get_required_attachments(offer, user, customized_paths)
        
        print(f"📎 Documentos que se adjuntarían:")
        for doc_path in required_attachments:
            doc_name = os.path.basename(doc_path)
            print(f"   ✅ {doc_name}")
        
        # Verificar que se adjuntan los documentos correctos
        expected_docs = {'test_application_form.pdf', 'test_cv.pdf', 'test_letter.pdf', 'test_degree.pdf'}
        actual_docs = {os.path.basename(doc_path) for doc_path in required_attachments}
        
        if actual_docs == expected_docs:
            print(f"✅ Test PASÓ: Se manejan correctamente los diccionarios")
        else:
            print(f"❌ Test FALLÓ:")
            print(f"   Esperado: {expected_docs}")
            print(f"   Actual: {actual_docs}")
            print(f"   Faltantes: {expected_docs - actual_docs}")
            print(f"   Extra: {actual_docs - expected_docs}")
            
    except Exception as e:
        print(f"❌ Test FALLÓ con error: {str(e)}")
    
    # Limpiar archivos temporales
    for doc_key, doc_path in user.documents.items():
        if isinstance(doc_path, dict):
            actual_path = doc_path['path']
        else:
            actual_path = doc_path
        try:
            os.remove(actual_path)
        except:
            pass
    
    print("🎉 Test completado!")

if __name__ == "__main__":
    asyncio.run(test_dict_error_fix()) 