#!/usr/bin/env python3
"""
Script para verificar la variedad de tipos de vacante que el scraper
puede extraer de una búsqueda general en Dublín.
"""
import asyncio
import sys
import os
import logging
from collections import Counter

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("verify_vacancy")

# Importar el scraper
from src.scrapers.scraper_educationposts import EducationPosts

# Condado de Dublin
COUNTY_ID = "27"
COUNTY_NAME = "Dublin"

async def verify_vacancy_types_in_dublin():
    """
    Verifica la variedad de tipos de vacante extraídos en una búsqueda general en Dublín.
    """
    logger.info(f"🔍 VERIFICANDO VARIEDAD DE TIPOS DE VACANTE EN {COUNTY_NAME.upper()}")
    logger.info("=" * 70)
    
    try:
        # Crear un scraper para una búsqueda general en Dublín (sin filtro de tipo de vacante)
        scraper = EducationPosts(
            level="primary", 
            county_id=COUNTY_ID,
            vacancy_type="", # Sin filtro de tipo de vacante
            max_workers=3,
            max_pages=2  # Analizar las primeras 2 páginas para tener una buena muestra
        )
        
        # Ejecutar búsqueda
        offers = await scraper.fetch_all()
        
        if not offers:
            logger.warning(f"ℹ️ No se encontraron ofertas en {COUNTY_NAME} en este momento.")
            return

        logger.info(f"Se encontraron {len(offers)} ofertas en total. Analizando las primeras 10 para verificar la variedad...")
        offers_to_check = offers[:10]

        all_vacancy_types = []
        for offer in offers_to_check:
            all_vacancy_types.append(offer.get("vacancy", "Desconocido"))

        # Contar la frecuencia de cada tipo de vacante
        type_counts = Counter(all_vacancy_types)

        # Resumen final
        logger.info("\n" + "=" * 70)
        logger.info("📊 RESUMEN DE TIPOS DE VACANTE ENCONTRADOS")
        logger.info("=" * 70)
        
        if not type_counts:
            logger.warning("No se pudo extraer ningún tipo de vacante.")
            return

        logger.info(f"Se encontraron {len(type_counts)} tipos de vacante únicos:")
        for tipo, cantidad in type_counts.items():
            logger.info(f"  • '{tipo}': {cantidad} veces")

        # Conclusión
        if len(type_counts) > 1:
            logger.info("\n✅ ¡Éxito! El scraper está extrayendo una variedad de tipos de vacante y no los agrupa todos en uno solo.")
        else:
            logger.warning("\n⚠️ El scraper solo encontró un tipo de vacante. Esto podría ser correcto si solo hay un tipo de oferta disponible, o podría indicar un problema si se esperaba más variedad.")

    except Exception as e:
        logger.error(f"❌ Ocurrió un error durante la verificación: {str(e)}")

if __name__ == "__main__":
    asyncio.run(verify_vacancy_types_in_dublin()) 