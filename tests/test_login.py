#!/usr/bin/env python3
"""
Script para probar el login en EducationPosts.ie
"""
import asyncio
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
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("login_test")

# Importar el scraper
from src.scrapers.scraper_educationposts import EducationPosts, BASE

async def test_login():
    """
    Prueba la funcionalidad de login
    """
    # Credenciales (actualiza con tus credenciales reales)
    username = "sonia.valencia.sonia@gmail.com"
    password = "Irlanda-2022"
    
    print(f"\n🔒 Probando login con usuario: {username}")
    
    # Crear instancia del scraper con las credenciales
    scraper = EducationPosts(username=username, password=password)
    
    # Crear sesión HTTP
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # Intentar login
        login_success = await scraper.login(session=session)
        
        if login_success:
            print("✅ Login exitoso!")
            print(f"🍪 Cookies obtenidas: {len(scraper.cookies)} cookies")
            
            # Verificar que tenemos acceso a páginas protegidas
            print("\n🔍 Verificando acceso a contenido...")
            
            # Intentar acceder a la página principal con las cookies de sesión
            try:
                async with session.get(f"{BASE}/", cookies=scraper.cookies) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Verificar si estamos logueados buscando elementos de usuario
                        import re
                        
                        # Buscar un texto que normalmente aparece cuando estás logueado
                        # (esto puede cambiar según el sitio)
                        if "Log Out" in html or "Profile" in html or "My Account" in html:
                            print("✅ Acceso verificado: Sesión autenticada correctamente")
                        else:
                            print("⚠️ Pudo acceder a la página, pero no se detectó sesión activa")
                            
                    else:
                        print(f"❌ Error al acceder a la página: Status {response.status}")
            except Exception as e:
                print(f"❌ Error verificando acceso: {str(e)}")
                
        else:
            print("❌ Login fallido. Revisa las credenciales e intenta nuevamente.")
            
    return login_success

if __name__ == "__main__":
    print("=" * 70)
    print("🔒 PRUEBA DE LOGIN EN EDUCATIONPOSTS.IE")
    print("=" * 70)
    
    try:
        asyncio.run(test_login())
    except KeyboardInterrupt:
        print("Prueba interrumpida por el usuario.")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
