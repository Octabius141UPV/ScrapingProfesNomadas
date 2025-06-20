#!/usr/bin/env python3
"""
Script avanzado para extraer ofertas de trabajo de EducationPosts.ie
con autenticación y procesamiento de datos detallado.
"""
import asyncio
import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
load_dotenv()

# Configurar logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(
            log_dir,
            f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ))
    ]
)
logger = logging.getLogger("scraper")

# Importar el scraper mejorado
from src.scrapers.scraper_educationposts import EducationPosts

async def extract_and_process_jobs(args):
    """
    Extrae y procesa las ofertas de trabajo según los argumentos proporcionados
    """
    # Siempre usamos las credenciales del archivo .env
    username = os.getenv("EDUCATIONPOSTS_USERNAME")
    password = os.getenv("EDUCATIONPOSTS_PASSWORD")
    
    # Si se especificó forzar credenciales por línea de comandos y el flag está activo
    if args.forzar_credenciales:
        if args.usuario:
            username = args.usuario
        if args.password:
            password = args.password
            
    # Verificar credenciales si se requiere login
    if not args.sin_login and (not username or not password):
        logger.error("❌ Error: Se solicitó login pero no se encontraron credenciales en .env")
        logger.error("   Verifica el archivo .env y asegúrate de que contiene EDUCATIONPOSTS_USERNAME y EDUCATIONPOSTS_PASSWORD")
        return False
    
    # Mostrar configuración inicial
    logger.info("=" * 80)
    logger.info("🔍 EXTRACCIÓN DE OFERTAS DE TRABAJO DE EDUCATIONPOSTS.IE")
    logger.info("=" * 80)
    logger.info(f"📊 Configuración:")
    logger.info(f"• Nivel educativo: {args.nivel}")
    logger.info(f"• Condado: {args.condado if args.condado else 'Todos'}")
    logger.info(f"• Tipo de vacante: {args.tipo_vacante if args.tipo_vacante else 'Todas'}")
    logger.info(f"• Máximo de páginas: {args.paginas if args.paginas else 'Todas'}")
    logger.info(f"• Autenticación: {'Desactivada' if args.sin_login else 'Activada'}")
    logger.info(f"• Modo depuración: {'Activado' if args.debug else 'Desactivado'}")
    logger.info("-" * 80)
    
    try:
        # Crear instancia del scraper
        scraper = EducationPosts(
            level=args.nivel,
            county_id=args.condado,
            vacancy_type=args.tipo_vacante,
            max_workers=args.workers,
            max_pages=args.paginas,
            username=None if args.sin_login else username,
            password=None if args.sin_login else password
        )
        
        # Iniciar el proceso de scraping
        start_time = datetime.now()
        logger.info(f"⏱️ Inicio del proceso: {start_time.strftime('%H:%M:%S')}")
        
        # Extraer ofertas de trabajo (con login si está configurado)
        ofertas = await scraper.fetch_all(max_pages=args.paginas, login_first=not args.sin_login)
        
        # Calcular tiempo de ejecución
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"⏱️ Proceso completado en {duration:.1f} segundos")
        
        # Verificar resultados
        if not ofertas:
            logger.warning("⚠️ No se encontraron ofertas que cumplan con los criterios")
            return False
        
        # Guardar resultados
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ofertas_{args.nivel}_{args.condado or 'todos'}_{timestamp}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Guardar en formato JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ofertas, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Resultados guardados en: {filepath}")
        
        # Mostrar estadísticas
        logger.info("\n📊 ESTADÍSTICAS:")
        logger.info(f"• Ofertas encontradas con email: {len(ofertas)}")
        
        # Por condado
        by_county = {}
        for oferta in ofertas:
            county = oferta.get("county", "Desconocido")
            by_county[county] = by_county.get(county, 0) + 1
        
        logger.info("\n📍 TOP CONDADOS:")
        for county, count in sorted(by_county.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"• {county}: {count} ofertas")
        
        # Por tipo de vacante
        by_vacancy = {}
        for oferta in ofertas:
            vacancy = oferta.get("vacancy", "Desconocido")
            by_vacancy[vacancy] = by_vacancy.get(vacancy, 0) + 1
        
        logger.info("\n👨‍🏫 TOP TIPOS DE VACANTE:")
        for vacancy, count in sorted(by_vacancy.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"• {vacancy}: {count} ofertas")
            
        # Ejemplo de algunas ofertas
        if len(ofertas) > 0:
            logger.info("\n📝 EJEMPLOS DE OFERTAS:")
            for i, oferta in enumerate(ofertas[:3], 1):
                logger.info(f"\n--- OFERTA {i} ---")
                logger.info(f"• Escuela: {oferta.get('school', 'N/A')}")
                logger.info(f"• Vacante: {oferta.get('vacancy', 'N/A')}")
                logger.info(f"• Condado: {oferta.get('county', 'N/A')}")
                logger.info(f"• Email: {oferta.get('email', 'N/A')}")
                logger.info(f"• Fecha límite: {oferta.get('deadline', 'N/A')}")
                logger.info(f"• URL: {oferta.get('url', 'N/A')}")
        
        logger.info("\n✅ Proceso completado con éxito")
        return True
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Proceso interrumpido por el usuario")
        return False
    except Exception as e:
        logger.error(f"\n❌ Error durante el proceso: {str(e)}", exc_info=True)
        return False

def main():
    """Función principal para ejecutar desde línea de comandos"""
    parser = argparse.ArgumentParser(description='Extractor avanzado de ofertas de EducationPosts.ie')
    
    # Opciones generales
    parser.add_argument('--nivel', type=str, default='primary', 
                      help='Nivel educativo (primary, second_level, etc)')
    parser.add_argument('--condado', type=str, default='', 
                      help='ID del condado (vacío=todos, 4=Cork, 27=Dublin)')
    parser.add_argument('--tipo-vacante', type=str, default='', 
                      help='Código de tipo de vacante (vacío=todas, 11=Principal, 7=Mainstream, 5=Special Ed, 61=SNA, 74=Deputy, 10=Resource, 17=Assistant)')
    parser.add_argument('--paginas', type=int, default=None, 
                      help='Número máximo de páginas a procesar (None=todas)')
    parser.add_argument('--workers', type=int, default=6, 
                      help='Máximo de workers concurrentes')
    
    # Opciones de autenticación
    parser.add_argument('--sin-login', action='store_true', 
                      help='Ejecutar sin iniciar sesión')
    parser.add_argument('--usuario', type=str, 
                      help='Usuario para login (email)')
    parser.add_argument('--password', type=str, 
                      help='Contraseña para login')
    parser.add_argument('--forzar-credenciales', action='store_true',
                      help='Forzar el uso de credenciales por línea de comandos en lugar de .env')
    
    # Opciones adicionales
    parser.add_argument('--debug', action='store_true', 
                      help='Activar modo debug')
    
    args = parser.parse_args()
    
    # Configurar nivel de log según modo debug
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("edu").setLevel(logging.DEBUG)
    
    # Ejecutar el proceso principal
    asyncio.run(extract_and_process_jobs(args))

if __name__ == "__main__":
    main()
