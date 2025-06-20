#!/usr/bin/env python3
"""
Script para probar el scraper con control de paginación
"""
import asyncio
import argparse
import json
import sys
import os
import logging
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs",
            "scraper_paginas.log"
        ))
    ]
)
logger = logging.getLogger("paginacion")

# Importar el scraper
from src.scrapers.scraper_educationposts import EducationPosts

async def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Control de paginación del scraper')
    parser.add_argument('--paginas', type=int, default=None, help='Número máximo de páginas a procesar (None=todas)')
    parser.add_argument('--nivel', type=str, default='primary', help='Nivel educativo (primary, second_level, etc)')
    parser.add_argument('--condado', type=str, default='', help='ID del condado (vacío=todos, 4=Cork, 27=Dublin)')
    parser.add_argument('--workers', type=int, default=6, help='Máximo de workers concurrentes')
    parser.add_argument('--debug', action='store_true', help='Activar modo debug')
    parser.add_argument('--sin-login', action='store_true', help='Ejecutar sin iniciar sesión')
    parser.add_argument('--usuario', type=str, help='Usuario para login (email)')
    parser.add_argument('--password', type=str, help='Contraseña para login')
    
    args = parser.parse_args()
    
    # Configuración de log según argumentos
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("edu").setLevel(logging.DEBUG)
        logger.debug("Modo debug activado")

    try:
        # Obtener credenciales
        username = args.usuario if args.usuario else os.getenv("EDUCATIONPOSTS_USERNAME")
        password = args.password if args.password else os.getenv("EDUCATIONPOSTS_PASSWORD")
        
        # Mostrar configuración
        logger.info("=" * 70)
        logger.info("🔍 PRUEBA DE SCRAPER CON CONTROL DE PAGINACIÓN")
        logger.info("=" * 70)
        logger.info(f"Nivel: {args.nivel}")
        logger.info(f"Condado: {args.condado if args.condado else 'Todos'}")
        logger.info(f"Máximo de páginas: {args.paginas if args.paginas else 'Todas'}")
        logger.info(f"Workers concurrentes: {args.workers}")
        
        # Información de autenticación
        if args.sin_login:
            logger.info("Modo: Sin autenticación")
        else:
            logger.info(f"Autenticación: {'Habilitada' if username and password else 'No disponible (sin credenciales)'}")
        
        logger.info("-" * 70)
        
        # Crear instancia del scraper
        scraper = EducationPosts(
            level=args.nivel,
            county_id=args.condado,
            max_workers=args.workers,
            username=None if args.sin_login else username,
            password=None if args.sin_login else password
        )
        
        # Ejecutar el scraper
        start_time = datetime.now()
        logger.info(f"Iniciando scraper: {start_time.strftime('%H:%M:%S')}")
        
        # Obtener ofertas
        ofertas = await scraper.fetch_all(max_pages=args.paginas, login_first=not args.sin_login)
        
        # Mostrar resumen
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("-" * 70)
        logger.info(f"✅ Scraping completado en {duration:.1f} segundos")
        logger.info(f"📊 Ofertas encontradas: {len(ofertas)}")
        
        # Guardar resultados en un archivo JSON
        if ofertas:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ofertas_{args.nivel}_{timestamp}.json"
            filepath = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                filename
            )
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(ofertas, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Resultados guardados en: {filepath}")
            
            # Mostrar algunas estadísticas
            by_county = {}
            for oferta in ofertas:
                county = oferta.get("county", "Desconocido")
                by_county[county] = by_county.get(county, 0) + 1
            
            logger.info("\n=== DISTRIBUCIÓN POR CONDADO ===")
            for county, count in sorted(by_county.items(), key=lambda x: x[1], reverse=True)[:10]:
                logger.info(f"- {county}: {count} ofertas")
            
            return True
        else:
            logger.warning("❌ No se encontraron ofertas")
            return False
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Proceso interrumpido por el usuario")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    asyncio.run(main())
