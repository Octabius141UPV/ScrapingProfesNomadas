#!/usr/bin/env python3
"""
Script de pruebas para ScrapingProfesNomadas
Permite probar componentes individuales sin ejecutar el bot completo
"""

import asyncio
import logging
import sys
import os

# Añadir directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper_educationposts import EducationPostsScraper
from email_sender import EmailSender
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_scraper():
    """Prueba el scraper de EducationPosts"""
    print("\n🔍 Probando scraper de EducationPosts...")
    
    scraper = EducationPostsScraper()
    
    try:
        # Hacer scraping de pocas ofertas para prueba
        offers = await scraper.scrape_offers()
        
        print(f"✅ Scraping completado. Ofertas encontradas: {len(offers)}")
        
        # Mostrar primeras ofertas
        for i, offer in enumerate(offers[:3]):
            print(f"\n--- Oferta {i+1} ---")
            print(f"Escuela: {offer.get('school_name', 'N/A')}")
            print(f"Posición: {offer.get('position', 'N/A')}")
            print(f"Nivel: {offer.get('level', 'N/A')}")
            print(f"Condado: {offer.get('county', 'N/A')}")
            print(f"Email: {offer.get('email', 'N/A')}")
            print(f"URL: {offer.get('url', 'N/A')}")
            
        return offers
        
    except Exception as e:
        print(f"❌ Error en scraper: {str(e)}")
        return []

async def test_email_sender():
    """Prueba el enviador de emails con 10 vacantes distintas"""
    print("\n📧 Probando enviador de emails con 10 vacantes...")
    
    # Verificar variables de entorno
    if not os.getenv('EMAIL_ADDRESS') or not os.getenv('EMAIL_PASSWORD'):
        print("❌ Variables EMAIL_ADDRESS y EMAIL_PASSWORD no configuradas")
        return False
        
    try:
        email_sender = EmailSender()
        test_recipient = os.getenv('EMAIL_ADDRESS')

        # Obtener 10 vacantes con email válido
        scraper = EducationPostsScraper()
        offers = await scraper.scrape_offers()
        valid_offers = [offer for offer in offers if offer.get('email')]
        selected_offers = valid_offers[:10]

        if not selected_offers:
            print("❌ No se encontraron vacantes con email válido")
            return False

        results = []
        for idx, offer in enumerate(selected_offers, 1):
            # Personalizar el asunto/cuerpo si se desea
            print(f"Enviando email de prueba {idx} para la vacante: {offer.get('school_name', 'N/A')} - {offer.get('position', 'N/A')}")
            success = await email_sender.send_test_email(test_recipient)
            results.append(success)
            if success:
                print(f"✅ Email de prueba {idx} enviado exitosamente a {test_recipient}")
            else:
                print(f"❌ Error enviando email de prueba {idx}")
        
        return all(results)
        
    except Exception as e:
        print(f"❌ Error en email sender: {str(e)}")
        return False

async def test_full_process():
    """Prueba el proceso completo con datos simulados"""
    print("\n🚀 Probando proceso completo...")
    
    # Datos de usuario simulados
    user_data = {
        'name': 'Juan Pérez',
        'email': 'juan.perez@ejemplo.com',
        'documents': [],
        'chat_id': 12345
    }
    
    try:
        # 1. Hacer scraping
        print("1. Haciendo scraping...")
        scraper = EducationPostsScraper()
        offers = await scraper.scrape_offers()
        
        if not offers:
            print("❌ No se encontraron ofertas")
            return False
            
        print(f"✅ Encontradas {len(offers)} ofertas")
        
        # 2. Filtrar ofertas con email
        valid_offers = [offer for offer in offers if offer.get('email')]
        print(f"✅ Ofertas con email válido: {len(valid_offers)}")
        
        if not valid_offers:
            print("❌ No hay ofertas con email válido")
            return False
            
        # 3. Probar generación de email (sin enviar)
        email_sender = EmailSender()
        
        # Tomar primera oferta como ejemplo
        test_offer = valid_offers[0]
        
        subject = email_sender._generate_subject(user_data, test_offer)
        body = email_sender._generate_email_body(user_data, test_offer)
        
        print(f"\n--- Email generado para {test_offer['school_name']} ---")
        print(f"Para: {test_offer['email']}")
        print(f"Asunto: {subject}")
        print(f"Cuerpo (primeros 200 chars): {body[:200]}...")
        
        print("\n✅ Proceso completo probado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en proceso completo: {str(e)}")
        return False

async def main():
    """Función principal de pruebas"""
    print("🧪 ScrapingProfesNomadas - Script de Pruebas")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Menú de opciones
    while True:
        print("\n¿Qué quieres probar?")
        print("1. Scraper de EducationPosts")
        print("2. Enviador de emails")
        print("3. Proceso completo (sin enviar emails)")
        print("4. Salir")
        
        choice = input("\nSelecciona una opción (1-4): ").strip()
        
        if choice == "1":
            await test_scraper()
            
        elif choice == "2":
            await test_email_sender()
            
        elif choice == "3":
            await test_full_process()
            
        elif choice == "4":
            print("👋 ¡Hasta luego!")
            break
            
        else:
            print("❌ Opción no válida")
            
        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Script interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
