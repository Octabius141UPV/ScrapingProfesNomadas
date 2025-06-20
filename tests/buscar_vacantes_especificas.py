#!/usr/bin/env python3
"""
Script para buscar tipos específicos de vacantes en Cork y Dublin
Busca solo los códigos: vc=11, vc=7, vc=5, vc=61, vc=74, vc=10, vc=17
Limitado a condados: Cork (ID=4) y Dublin (ID=27)
"""
import asyncio
import sys
import os
import json
import logging
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("vacantes_especificas")

# Importar el scraper
from src.scrapers.scraper_educationposts import EducationPosts, VACANCY_TYPES

# Códigos de vacantes específicos a buscar
VACANCY_CODES = ["11", "7", "5", "61", "74", "10", "17"]

# Condados específicos: Cork y Dublin
COUNTIES = {
    "4": "Cork",
    "27": "Dublin"
}

async def buscar_vacantes_especificas():
    """
    Busca ofertas para tipos específicos de vacantes en Cork y Dublin
    """
    logger.info("🔍 BÚSQUEDA DE VACANTES ESPECÍFICAS EN CORK Y DUBLIN")
    logger.info("=" * 70)
    
    # Mostrar los tipos de vacantes que vamos a buscar
    logger.info("📋 Tipos de vacantes a buscar:")
    for code in VACANCY_CODES:
        vacancy_name = VACANCY_TYPES.get(code, f"Código {code}")
        logger.info(f"  • VC={code}: {vacancy_name}")
    
    logger.info("\n📍 Condados a buscar:")
    for county_id, county_name in COUNTIES.items():
        logger.info(f"  • ID={county_id}: {county_name}")
    
    logger.info("-" * 70)
    
    todas_las_ofertas = []
    
    # Buscar en cada condado y cada tipo de vacante
    for county_id, county_name in COUNTIES.items():
        logger.info(f"\n🏠 BUSCANDO EN {county_name.upper()}")
        logger.info("=" * 50)
        
        for vacancy_code in VACANCY_CODES:
            vacancy_name = VACANCY_TYPES.get(vacancy_code, f"Código {vacancy_code}")
            
            logger.info(f"\n🔎 {county_name} - {vacancy_name} (VC={vacancy_code})")
            logger.info("-" * 40)
            
            try:
                # Crear scraper para este tipo de vacante y condado específico
                scraper = EducationPosts(
                    level="primary", 
                    county_id=county_id,  # Cork o Dublin
                    vacancy_type=vacancy_code,
                    max_workers=4,
                    max_pages=3  # Limitar a 3 páginas por combinación
                )
                
                # Ejecutar búsqueda
                start_time = datetime.now()
                ofertas = await scraper.fetch_all(max_pages=3, login_first=True)
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                logger.info(f"⏱️ Tiempo: {duration:.1f}s")
                logger.info(f"📧 Ofertas encontradas: {len(ofertas)}")
                
                # Añadir información adicional a cada oferta
                for oferta in ofertas:
                    oferta["vacancy_code"] = vacancy_code
                    oferta["vacancy_type_name"] = vacancy_name
                    oferta["target_county_id"] = county_id
                    oferta["target_county_name"] = county_name
                
                todas_las_ofertas.extend(ofertas)
                
                # Mostrar algunas ofertas como ejemplo
                if ofertas:
                    logger.info("📝 Primeras ofertas:")
                    for i, oferta in enumerate(ofertas[:2], 1):
                        logger.info(f"  {i}. {oferta.get('school', 'N/A')} - {oferta.get('vacancy', 'N/A')}")
                else:
                    logger.info("  ℹ️ No se encontraron ofertas para esta combinación")
                
            except Exception as e:
                logger.error(f"❌ Error al buscar {vacancy_name} en {county_name}: {str(e)}")
            
            # Pausa entre búsquedas para no sobrecargar el servidor
            await asyncio.sleep(1)
        
        # Pausa más larga entre condados
        await asyncio.sleep(3)
    
    # Resumen final
    logger.info("\n" + "=" * 70)
    logger.info("📊 RESUMEN FINAL - CORK Y DUBLIN")
    logger.info("=" * 70)
    logger.info(f"Total de ofertas encontradas: {len(todas_las_ofertas)}")
    
    # Estadísticas por condado objetivo
    by_target_county = {}
    for oferta in todas_las_ofertas:
        target_county = oferta.get("target_county_name", "Desconocido")
        by_target_county[target_county] = by_target_county.get(target_county, 0) + 1
    
    logger.info("\n📍 Por condado objetivo:")
    for county, count in sorted(by_target_county.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  • {county}: {count} ofertas")
    
    # Estadísticas por tipo de vacante
    by_vacancy_type = {}
    for oferta in todas_las_ofertas:
        vtype = oferta.get("vacancy_type_name", "Desconocido")
        by_vacancy_type[vtype] = by_vacancy_type.get(vtype, 0) + 1
    
    logger.info("\n📋 Por tipo de vacante:")
    for vtype, count in sorted(by_vacancy_type.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  • {vtype}: {count} ofertas")
    
    # Estadísticas por condado real (de las ofertas encontradas)
    by_actual_county = {}
    for oferta in todas_las_ofertas:
        county = oferta.get("county", "Desconocido")
        by_actual_county[county] = by_actual_county.get(county, 0) + 1
    
    logger.info("\n📍 Por condado real de las ofertas:")
    for county, count in sorted(by_actual_county.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  • {county}: {count} ofertas")
    
    # Guardar resultados
    if todas_las_ofertas:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vacantes_cork_dublin_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(todas_las_ofertas, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Resultados guardados en: {filepath}")
    
    logger.info("\n✅ Búsqueda en Cork y Dublin completada")

if __name__ == "__main__":
    print("🚀 Iniciando búsqueda de vacantes específicas en Cork y Dublin...")
    asyncio.run(buscar_vacantes_especificas())
