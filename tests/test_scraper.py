#!/usr/bin/env python3
"""
Script de prueba para el scraper de EducationPosts.ie
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper_test.log')
    ]
)

logger = logging.getLogger(__name__)

# Importar el scraper
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.scrapers.scraper_educationposts import EducationPosts

async def test_scraper():
    """
    Función principal de prueba del scraper
    """
    logger.info("=== INICIANDO PRUEBA DEL SCRAPER ===")
    
    try:
        # Crear instancia del scraper
        scraper = EducationPosts(level="primary", county_id="")
        
        # Probar con una sola página primero
        logger.info("Probando scraping de 1 página...")
        offers = await scraper.fetch_all()
        
        logger.info(f"Total de ofertas encontradas: {len(offers)}")
        
        if offers:
            # Mostrar las primeras 3 ofertas como ejemplo
            logger.info("=== PRIMERAS OFERTAS ENCONTRADAS ===")
            for i, offer in enumerate(offers[:3], 1):
                logger.info(f"\n--- OFERTA {i} ---")
                logger.info(f"Escuela: {offer.get('school', 'N/A')}")
                logger.info(f"Vacante: {offer.get('vacancy', 'N/A')}")
                logger.info(f"Condado: {offer.get('county', 'N/A')}")
                logger.info(f"Fecha límite: {offer.get('deadline', 'N/A')}")
                logger.info(f"Email: {offer.get('email', 'NO ENCONTRADO')}")
                logger.info(f"ID: {offer.get('id', 'N/A')}")
                logger.info(f"URL: {offer.get('url', 'N/A')}")
                
                if offer.get('description'):
                    desc = offer['description'][:100] + "..." if len(offer['description']) > 100 else offer['description']
                    logger.info(f"Descripción: {desc}")
            
            # Guardar resultados en archivo JSON
            output_file = f"ofertas_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(offers, f, indent=2, ensure_ascii=False)
            
            logger.info(f"\n=== RESUMEN ===")
            logger.info(f"Total ofertas procesadas: {len(offers)}")
            logger.info(f"Ofertas con email: {len([o for o in offers if o.get('email')])}")
            logger.info(f"Ofertas sin email: {len([o for o in offers if not o.get('email')])}")
            logger.info(f"Resultados guardados en: {output_file}")
            
            # Análisis por nivel educativo
            by_level = {}
            for offer in offers:
                level = offer.get('level', 'Unknown')
                if level not in by_level:
                    by_level[level] = 0
                by_level[level] += 1
            
            logger.info(f"\n=== OFERTAS POR NIVEL ===")
            for level, count in by_level.items():
                logger.info(f"{level}: {count} ofertas")
            
        else:
            logger.warning("No se encontraron ofertas. Revisar la configuración del scraper.")
            
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        return False
    
    logger.info("=== PRUEBA COMPLETADA ===")
    return len(offers) > 0 if offers else False

async def test_single_url():
    """
    Prueba específica de una URL individual
    """
    logger.info("=== PRUEBA DE URL INDIVIDUAL ===")
    
    # Probar URL de primary level
    test_url = "https://www.educationposts.ie/posts/primary_level?sb=application_closing_date&sd=0&p=1&cy=&pd=&vc=&ptl=&ga=0"
    
    try:
        import aiohttp
        from src.scrapers.scraper_educationposts import HEAD
        
        async with aiohttp.ClientSession(headers=HEAD) as session:
            async with session.get(test_url) as response:
                if response.status == 200:
                    logger.info(f"✅ Conexión exitosa a: {test_url}")
                    logger.info(f"Status code: {response.status}")
                    
                    # Obtener el contenido
                    html = await response.text()
                    logger.info(f"Content length: {len(html)} caracteres")
                    
                    # Verificar si contiene la tabla esperada
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Buscar tabla desktop
                    desktop_table = soup.find('table', {'id': 'tblAdverts', 'class': 'd-none d-lg-table'})
                    if desktop_table:
                        logger.info("✅ Tabla desktop encontrada")
                        tbody = desktop_table.find('tbody')
                        if tbody:
                            rows = tbody.find_all('tr')
                            logger.info(f"✅ {len(rows)} filas encontradas en la tabla")
                        else:
                            logger.warning("⚠️ No se encontró tbody en la tabla")
                    else:
                        logger.warning("⚠️ No se encontró tabla desktop")
                    
                    # Buscar tabla móvil
                    mobile_table = soup.find('table', {'class': 'mobileTable d-lg-none'})
                    if mobile_table:
                        logger.info("✅ Tabla móvil encontrada")
                    else:
                        logger.warning("⚠️ No se encontró tabla móvil")
                else:
                    logger.error(f"❌ No se pudo conectar a: {test_url}. Status: {response.status}")
    except Exception as e:
        logger.error(f"❌ Error probando URL individual: {str(e)}")

def main():
    """
    Función principal
    """
    print("🚀 Iniciando pruebas del scraper de EducationPosts.ie...")
    print("📋 Esta prueba verificará:")
    print("   1. Conexión a la página")
    print("   2. Extracción de ofertas")
    print("   3. Búsqueda de emails de contacto")
    print("   4. Guardado de resultados")
    print("-" * 50)
    
    # Ejecutar pruebas
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Prueba básica de URL
        loop.run_until_complete(test_single_url())
        print("-" * 50)
        
        # Prueba completa del scraper
        success = loop.run_until_complete(test_scraper())
        
        if success:
            print("\n✅ ¡Prueba exitosa! El scraper está funcionando correctamente.")
        else:
            print("\n❌ La prueba falló. Revisar los logs para más detalles.")
            
    except KeyboardInterrupt:
        print("\n⏹️ Prueba interrumpida por el usuario.")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
