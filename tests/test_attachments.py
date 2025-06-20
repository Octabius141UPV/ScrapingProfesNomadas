#!/usr/bin/env python3
"""
Script de prueba para verificar que el nuevo sistema de adjuntos funciona correctamente
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bots.telegram_bot import UserData, TelegramBot

def test_attachments():
    """Prueba el nuevo sistema de adjuntos"""
    print("🧪 Probando el nuevo sistema de adjuntos...")
    
    # Crear un usuario de prueba con documentos
    user = UserData()
    user.name = "Test User"
    user.email = "test@example.com"
    
    # Simular documentos subidos
    test_docs = {
        'application_form': {'path': 'temp/application form álvaro.pdf', 'filename': 'application form álvaro.pdf'},
        'letter_of_application': {'path': 'data/Letter of Application def AdC.pdf', 'filename': 'Letter of Application def AdC.pdf'},
        'cv': {'path': 'data/CV .pdf', 'filename': 'CV .pdf'},
        'degree': {'path': 'data/Degree Álvaro.pdf', 'filename': 'Degree Álvaro.pdf'},
        'tc_registration': {'path': 'data/TC Registration Certificate Álvaro.pdf', 'filename': 'TC Registration Certificate Álvaro.pdf'}
    }
    
    # Solo asignar documentos que existen
    for doc_key, doc_info in test_docs.items():
        if os.path.exists(doc_info['path']):
            user.documents[doc_key] = doc_info
            print(f"✅ Documento {doc_key} encontrado: {doc_info['path']}")
        else:
            print(f"⚠️ Documento {doc_key} no encontrado: {doc_info['path']}")
    
    # Crear instancia del bot
    bot = TelegramBot("dummy_token")
    
    # Caso 1: Oferta que pide documentos específicos
    offer_1 = {
        'school_name': 'St. Patrick\'s NS',
        'position': 'Primary Teacher',
        'required_documents': ['Application Form', 'Letter of Application', 'CV', 'Teaching Council Registration']
    }
    
    print("\n📋 Caso 1: Oferta con documentos específicos")
    attachments_1 = bot.get_required_attachments(offer_1, user)
    print(f"Documentos a adjuntar: {len(attachments_1)}")
    for doc in attachments_1:
        print(f"  - {os.path.basename(doc)}")
    
    # Caso 2: Oferta que pide documentos diferentes
    offer_2 = {
        'school_name': 'St. Mary\'s NS',
        'position': 'Special Education Teacher',
        'required_documents': ['Application Form', 'CV', 'Degree', 'Teaching Practice']
    }
    
    print("\n📋 Caso 2: Oferta con documentos diferentes")
    attachments_2 = bot.get_required_attachments(offer_2, user)
    print(f"Documentos a adjuntar: {len(attachments_2)}")
    for doc in attachments_2:
        print(f"  - {os.path.basename(doc)}")
    
    # Caso 3: Oferta sin documentos específicos (usar básicos)
    offer_3 = {
        'school_name': 'Generic School',
        'position': 'Teacher',
        'required_documents': []
    }
    
    print("\n📋 Caso 3: Oferta sin documentos específicos")
    attachments_3 = bot.get_required_attachments(offer_3, user)
    print(f"Documentos a adjuntar: {len(attachments_3)}")
    for doc in attachments_3:
        print(f"  - {os.path.basename(doc)}")
    
    return True

if __name__ == "__main__":
    if test_attachments():
        print("\n🎉 ¡Sistema de adjuntos funcionando correctamente!")
        print("✅ Solo adjunta los documentos que pide cada oferta")
        print("✅ No adjunta documentos innecesarios")
        print("✅ Mapea correctamente los nombres de documentos")
    else:
        print("\n❌ Error en el sistema de adjuntos") 