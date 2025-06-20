#!/usr/bin/env python3
"""
Script de prueba simple para verificar la extracción de URLs de EducationPosts.ie
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import logging

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("url_test")

# Encabezados HTTP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# URL base
BASE = "https://www.educationposts.ie"

async def test_url_extraction():
    """
    Prueba específica para extraer URLs de ofertas
    """
    logger.info("=== PRUEBA DE EXTRACCIÓN DE URLS ===")
    
    # URL de prueba
    test_url = "https://www.educationposts.ie/posts/primary_level?sb=application_closing_date&sd=0&p=1&cy=&pd=&vc=&ptl=&ga=0"
    
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            logger.info(f"Conectando a: {test_url}")
            async with session.get(test_url) as response:
                if response.status == 200:
                    logger.info(f"✅ Conexión exitosa. Status code: {response.status}")
                    
                    # Obtener contenido
                    html = await response.text()
                    logger.info(f"Contenido HTML recibido: {len(html)} caracteres")
                    
                    # Analizar con BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # --- Analizar tabla desktop ---
                    logger.info("\n=== ANALIZANDO TABLA DESKTOP ===")
                    tbl = soup.find("table", id="tblAdverts", class_="d-none d-lg-table")
                    if tbl and tbl.tbody:
                        rows = tbl.tbody.find_all("tr")
                        logger.info(f"✅ Encontradas {len(rows)} filas en la tabla desktop")
                        
                        # Mostrar primeras 3 filas
                        for i, tr in enumerate(rows[:3], 1):
                            logger.info(f"\n--- FILA {i} ---")
                            
                            # Verificar data-href
                            data_href = tr.get("data-href")
                            logger.info(f"data-href en <tr>: {data_href or 'NO ENCONTRADO'}")
                            
                            # Buscar enlaces en la fila
                            tds = tr.find_all("td")
                            if tds and len(tds) > 1:
                                links = tds[1].find_all("a")
                                for j, a in enumerate(links, 1):
                                    logger.info(f"Enlace {j} href: {a.get('href')}")
                                    logger.info(f"Enlace {j} texto: {a.text.strip()}")
                            
                            # Extraer ID y escuela
                            if len(tds) >= 2:
                                logger.info(f"ID: {tds[0].text.strip() if tds[0] else 'N/A'}")
                                logger.info(f"Escuela: {tds[1].text.strip() if tds[1] else 'N/A'}")
                    else:
                        logger.warning("❌ No se encontró la tabla desktop")
                    
                    # --- Analizar tabla móvil ---
                    logger.info("\n=== ANALIZANDO TABLA MÓVIL ===")
                    mt = soup.select_one("table.mobileTable")
                    if mt:
                        rows = mt.find_all("tr")
                        logger.info(f"✅ Encontradas {len(rows)} filas en la tabla móvil")
                        
                        # Mostrar primeras 3 filas
                        for i, tr in enumerate(rows[:3], 1):
                            logger.info(f"\n--- FILA MÓVIL {i} ---")
                            
                            # Verificar data-href
                            data_href = tr.get("data-href")
                            logger.info(f"data-href en <tr>: {data_href or 'NO ENCONTRADO'}")
                            
                            # Mostrar estructura
                            card = tr.find("td")
                            if card:
                                # Buscar datos de escuela
                                for div in card.find_all("div", class_="mobileRow")[:2]:
                                    lab = div.select_one(".mobileLabel")
                                    val = div.select_one(".mobileData")
                                    if lab and val:
                                        logger.info(f"{lab.text.strip()}: {val.text.strip()}")
                    else:
                        logger.warning("❌ No se encontró la tabla móvil")
                else:
                    logger.error(f"❌ Error al conectar. Status: {response.status}")
    
    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {str(e)}", exc_info=True)
        return False
    
    logger.info("=== PRUEBA COMPLETADA ===")
    return True

if __name__ == "__main__":
    print("🔍 Iniciando prueba de extracción de URLs de EducationPosts.ie")
    print("=" * 70)
    try:
        asyncio.run(test_url_extraction())
        print("\n✅ Prueba completada. Revisa los resultados arriba.")
    except Exception as e:
        print(f"\n❌ Error general: {str(e)}")
