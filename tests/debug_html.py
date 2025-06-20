#!/usr/bin/env python3
"""
Script de diagnóstico para revisar la estructura HTML de EducationPosts.ie
"""
import asyncio
import aiohttp
import sys
import os
from bs4 import BeautifulSoup

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

async def debug_html():
    """Diagnóstico de la estructura HTML"""
    
    # URL de prueba para nivel primario
    test_url = "https://www.educationposts.ie/posts/primary_level?sb=application_closing_date&sd=0&p=1&cy=&pd=&vc=&ptl=&ga=0"
    
    print("🔍 DIAGNÓSTICO DE ESTRUCTURA HTML")
    print("=" * 60)
    print(f"URL: {test_url}")
    print()
    
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(test_url) as response:
                print(f"Status: {response.status}")
                
                if response.status != 200:
                    print(f"❌ Error: Status code {response.status}")
                    return
                
                html = await response.text()
                print(f"HTML length: {len(html)} caracteres")
                
                # Analizar con BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                
                # Buscar diferentes tipos de tablas
                print("\n📋 BUSCANDO TABLAS...")
                
                # 1. Tabla desktop específica
                desktop_table = soup.find("table", id="tblAdverts", class_="d-none d-lg-table")
                print(f"Tabla desktop (id=tblAdverts): {'✅ Encontrada' if desktop_table else '❌ No encontrada'}")
                
                # 2. Tabla móvil específica
                mobile_table = soup.select_one("table.mobileTable")
                print(f"Tabla móvil (class=mobileTable): {'✅ Encontrada' if mobile_table else '❌ No encontrada'}")
                
                # 3. Cualquier tabla
                all_tables = soup.find_all("table")
                print(f"Total de tablas encontradas: {len(all_tables)}")
                
                # Mostrar información de todas las tablas
                if all_tables:
                    print("\n📊 DETALLES DE TABLAS:")
                    for i, table in enumerate(all_tables[:5], 1):  # Solo las primeras 5
                        print(f"\nTabla {i}:")
                        print(f"  ID: {table.get('id', 'Sin ID')}")
                        print(f"  Clases: {table.get('class', 'Sin clases')}")
                        rows = table.find_all("tr")
                        print(f"  Filas: {len(rows)}")
                        
                        # Mostrar primera fila con data-href si existe
                        for row in rows[:3]:
                            if row.has_attr("data-href"):
                                print(f"  Fila con data-href: {row['data-href']}")
                                break
                
                # 4. Buscar filas con data-href directamente
                rows_with_href = soup.find_all("tr", attrs={"data-href": True})
                print(f"\n🔗 Filas con data-href: {len(rows_with_href)}")
                
                if rows_with_href:
                    print("Primeras 3 URLs encontradas:")
                    for i, row in enumerate(rows_with_href[:3], 1):
                        print(f"  {i}. {row['data-href']}")
                
                # 5. Buscar elementos de paginación
                print(f"\n📄 PAGINACIÓN:")
                pagination = soup.select(".pagination")
                print(f"Elementos de paginación: {len(pagination)}")
                
                pagination_links = soup.select(".pagination a[data-page]")
                print(f"Enlaces de página: {len(pagination_links)}")
                
                if pagination_links:
                    pages = [int(a["data-page"]) for a in pagination_links if a.has_attr("data-page")]
                    if pages:
                        print(f"Páginas disponibles: {min(pages)} - {max(pages)}")
                
                # 6. Buscar contenido que indique si hay ofertas
                print(f"\n📝 CONTENIDO:")
                content_text = soup.get_text().lower()
                
                if "no job" in content_text or "no posts" in content_text:
                    print("⚠️ Posible mensaje de 'sin ofertas' detectado")
                
                if "job" in content_text or "post" in content_text:
                    print("✅ Contenido relacionado con trabajos detectado")
                
                # Guardar HTML para inspección manual si es necesario
                with open("/Users/raulfortea/Projects/ScrapingProfesNomadas/logs/debug_html.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"\n💾 HTML guardado en: logs/debug_html.html")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("Iniciando diagnóstico HTML...")
    asyncio.run(debug_html())
