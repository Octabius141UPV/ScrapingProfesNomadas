import asyncio, aiohttp, logging, random, re, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

BASE  = "https://www.educationposts.ie"
LOGIN_URL = f"{BASE}/auth/login"

# Añadir función auxiliar para el sufijo correcto en la URL
def get_level_url(level):
    if level in ["second_level", "pre_school"]:
        return level
    else:
        return f"{level}_level"

# Reemplazar en la construcción de la URL:
# url = BASE + LIST.format(level=self.level, ...)
# por:
# url = BASE + LIST.format(level_url=get_level_url(self.level), ...)

# Cambia la plantilla LIST:
# LIST  = "/posts/{level}_level?..."
# por:
LIST  = "/posts/{level_url}?sb=application_closing_date&sd=0&p={page}&cy={county}&pd={district}&vc={vacancy_type}&ptl=&ga=0"

HEAD  = {"User-Agent":
         ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/124.0.0.0 Safari/537.36"),
         "Accept": "*/*"}

# Mapeo de condados por ID (basado en la URL)
COUNTIES = {
    "": "Todos",
    "4": "Cork",
    "27": "Dublin",
    "13": "Galway",
    "9": "Kerry",
    "16": "Limerick",
    "30": "Waterford",
    "20": "Mayo",
    # Añadir más condados según se identifiquen
}

# Mapeo de tipos de vacantes por código VC
VACANCY_TYPES = {
    "": "Todas las vacantes",
    "11": "Principal Teacher",
    "7": "Mainstream Class Teacher", 
    "5": "Special Education Teacher",
    "61": "Special Needs Assistant",
    "74": "Deputy Principal",
    "10": "Resource Teacher",
    "17": "Assistant Principal"
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.I)
BAD_MAIL = ("noreply", "no-reply", "wordpress", "example.com", "educationposts.ie", "teachingcouncil.ie")

log = logging.getLogger("edu")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


# ------------- helpers -----------------------------------------------------------------
def first_valid_email(text: str) -> Optional[str]:
    for m in EMAIL_RE.findall(text or ""):
        if not any(b in m.lower() for b in BAD_MAIL):
            # Limpiar el email de cualquier texto adicional
            email = m.strip()
            # Eliminar cualquier texto que venga después del email
            if "Website" in email:
                email = email.split("Website")[0].strip()
            return email
    return None


async def rand_sleep(a=0.5, b=1.5, safe_mode=False):
    """
    Espera aleatoria para evitar detección.
    
    Args:
        a: Tiempo mínimo de espera en segundos
        b: Tiempo máximo de espera en segundos  
        safe_mode: Si es True, usa tiempos más largos para máxima seguridad
    """
    if safe_mode:
        # Modo seguro reducido: esperas más cortas pero seguras
        base_sleep = random.uniform(1.5, 3.0)
        # Agregar variabilidad extra ocasional pero menor
        if random.random() < 0.05:  # 5% de las veces espera extra
            base_sleep += random.uniform(2.0, 5.0)
        await asyncio.sleep(base_sleep)
    else:
        await asyncio.sleep(random.uniform(a, b))


def is_valid_vacancy(vacancy_name: str) -> bool:
    """
    Determina si una vacante cumple con los criterios de filtro:
    - Debe contener la palabra "teacher"
    - No debe ser "principal teacher"
    - No debe ser "special school teacher placement"
    - No debe contener "placement" junto con "teacher" y "special school"
    
    Args:
        vacancy_name: Nombre de la vacante a evaluar
        
    Returns:
        True si cumple con los criterios, False en caso contrario
    """
    if not vacancy_name:
        return False
    
    vacancy_lower = vacancy_name.lower()
    
    # Verificar que contiene "teacher"
    if "teacher" not in vacancy_lower:
        return False
    
    # Excluir "principal teacher"
    if "principal teacher" in vacancy_lower:
        return False
    
    # Excluir "special school teacher placement" - comprobación exacta
    if "special school teacher placement" in vacancy_lower:
        return False
        
    # Excluir combinaciones de palabras clave para "special school teacher placement"
    if "special school" in vacancy_lower and "placement" in vacancy_lower:
        return False
        
    # Excluir cualquier tipo de "placement"
    if "placement" in vacancy_lower and "teacher" in vacancy_lower:
        return False
    
    return True


# ------------- scraper -----------------------------------------------------------------
class EducationPosts:
    def __init__(self, level="primary", county_id="", district_id="", vacancy_type="", max_workers=3, max_pages=None, 
                 username=None, password=None, safe_mode=False):
        self.level     = level         # "primary", "second_level", etc.
        self.county_id = str(county_id) if county_id is not None else ""  # Asegurarse que sea string
        self.county_name = COUNTIES.get(self.county_id, "Desconocido")
        
        # Validar y configurar distrito (solo para Dublin)
        self.district_id = ""
        if self.county_id == "27":  # Si es Dublin
            district_id_str = str(district_id) if district_id is not None else ""
            if self.validate_district_id(district_id_str):
                self.district_id = district_id_str
                if district_id_str:
                    log.info(f"Filtro por distrito: {DUBLIN_DISTRICTS.get(district_id_str)}")
        
        self.vacancy_type = str(vacancy_type) if vacancy_type is not None else ""  # Código VC
        self.vacancy_name = VACANCY_TYPES.get(self.vacancy_type, "Desconocido")
        self.max_pages = max_pages     # None = todas las páginas
        
        # Configuración anti-detección
        self.safe_mode = safe_mode
        if safe_mode:
            # Modo seguro: menos trabajadores concurrentes y más esperas
            self.sem = asyncio.Semaphore(min(max_workers, 1))  # Solo 1 trabajador concurrente
            log.info("🛡️ Modo seguro activado: velocidad muy reducida para evitar detección")
        else:
            self.sem = asyncio.Semaphore(max_workers)
        
        # Credenciales (usar siempre .env, excepto que se especifique lo contrario)
        self.username = os.getenv("EDUCATIONPOSTS_USERNAME")
        self.password = os.getenv("EDUCATIONPOSTS_PASSWORD")
        
        # Sobrescribir con parámetros si se proporcionan explícitamente
        if username:
            self.username = username
        if password:
            self.password = password
            
        self.cookies = {}  # Guardaremos las cookies de sesión aquí
        self.is_logged_in = False
        
        log.info(f"Configurado scraper para nivel: {self.level}, condado: {self.county_name} (ID: {self.county_id}), tipo: {self.vacancy_name} (VC: {self.vacancy_type})")
        log.info("🔍 Filtrado avanzado de vacantes: Solo 'teacher', excluyendo 'principal teacher' y 'special school teacher placement'")

    # --------- PUBLIC ----------
    async def fetch_all(self, max_pages=None, login_first=True, limit=None) -> List[Dict]:
        """
        Obtiene todas las ofertas de trabajo.
        
        Args:
            max_pages: Número máximo de páginas a procesar. None para todas.
            login_first: Si es True, intenta iniciar sesión antes de hacer scraping.
            limit: Número máximo de ofertas a obtener. None para todas.
        
        Returns:
            Lista de ofertas con detalles y email.
        """
        # Crear una sesión HTTP con cookies persistentes
        cookies_jar = aiohttp.CookieJar()
        async with aiohttp.ClientSession(headers=HEAD, cookie_jar=cookies_jar) as s:
            # Iniciar sesión si se solicita
            if login_first and self.username and self.password:
                log.info("🔑 Intentando iniciar sesión...")
                login_success = await self.login(session=s)
                if login_success:
                    log.info("✅ Sesión iniciada correctamente")
                else:
                    log.error("❌ Error al iniciar sesión")
                    return []
                    
            # Determinar el número de páginas
            log.info("📊 Obteniendo número total de páginas...")
            total_pages = await self._get_pages(s)
            log.info(f"📚 Total páginas disponibles: {total_pages}")
            
            if total_pages == 0:
                log.error("❌ No se encontraron páginas disponibles")
                return []
            
            # Si hay un límite de páginas, respetarlo
            if max_pages and max_pages < total_pages:
                pages_to_process = max_pages
                log.info(f"📌 Limitando a {max_pages} páginas")
            else:
                pages_to_process = total_pages
                
            log.info(f"🔄 Procesando {pages_to_process} páginas...")

            # 1) Obtener URLs y datos básicos de todas las páginas
            basic = []
            for page_num in range(1, pages_to_process + 1):
                if limit and len(basic) >= limit:
                    log.info(f"📊 Límite de ofertas alcanzado: {limit}")
                    break
                
                log.info(f"📄 Procesando página {page_num}/{pages_to_process}...")
                page_offers = await self._extract_urls_from_page(s, page_num)
                if page_offers:
                    log.info(f"✅ Página {page_num}: {len(page_offers)} ofertas encontradas")
                    basic.extend(page_offers)
                else:
                    log.warning(f"⚠️ Página {page_num}: No se encontraron ofertas")
                
                # Espera entre páginas para evitar detección
                if page_num < pages_to_process:
                    wait_time = random.uniform(2.0, 4.0)
                    log.info(f"⏱️ Esperando {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
            
            log.info(f"📊 Total ofertas básicas encontradas: {len(basic)}")
            
            if not basic:
                log.error("❌ No se encontraron ofertas en ninguna página")
                return []

            # 2) Procesar cada oferta para obtener detalles
            log.info("🔍 Obteniendo detalles de las ofertas...")
            detailed_offers = []
            for i, offer in enumerate(basic[:limit] if limit else basic, 1):
                detailed = await self._offer_detail(s, offer.copy())
                if detailed:
                    # Loguear todos los campos relevantes antes de filtrar
                    log.info(f"[DEBUG] Oferta completa antes de filtrar: {detailed}")
                    school_name = detailed.get('school_name', '').lower()
                    if "gaelscoil" in school_name:
                        log.info(f"⛔ Oferta filtrada (Gaelscoil): {detailed.get('school_name', 'N/A')}")
                        continue
                    # Unifica todos los campos relevantes en un solo texto
                    all_text = ' '.join([
                        str(detailed.get('vacancy', '')),
                        str(detailed.get('additional information', '')),
                        str(detailed.get('description', '')),
                        str(detailed.get('requirements', '')),
                        str(detailed.get('required subject', '')),
                        str(detailed.get('subjects', ''))
                    ]).lower()
                    # Aplica el filtro robusto
                    if ("teacher" in all_text and
                        "principal teacher" not in all_text and
                        "special school teacher placement" not in all_text):
                        vacancy_name = "Teacher"
                    else:
                        log.info(f"⛔ Oferta filtrada (vacante no compatible): {all_text}")
                        continue
                    # El título de la oferta debe mostrar el nombre de la escuela y el tipo de vacante
                    detailed['vacancy'] = vacancy_name
                    detailed_offers.append(detailed)
                    log.info(f"✅ Oferta {i} procesada correctamente")
                else:
                    log.warning(f"⚠️ No se pudieron obtener detalles de la oferta {i}")
                
                # Espera entre ofertas
                if i < len(basic):
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            
            log.info(f"🎯 Total ofertas procesadas: {len(detailed_offers)}")
            
            return detailed_offers

    # --------- AUTHENTICATION ----------
    async def login(self, session=None) -> bool:
        """
        Inicia sesión en EducationPosts.ie usando las credenciales proporcionadas.
        
        Args:
            session: Sesión aiohttp existente (opcional)
            
        Returns:
            bool: True si el login fue exitoso, False en caso contrario
        """
        if not self.username or not self.password:
            log.warning("No se proporcionaron credenciales de login")
            return False
            
        log.info(f"Iniciando sesión con usuario: {self.username}")
        
        # Si no se proporciona una sesión, crear una nueva
        close_session = False
        if not session:
            session = aiohttp.ClientSession(headers=HEAD)
            close_session = True
            
        try:
            # Preparar los datos del formulario
            form_data = {
                "returnTo": "",
                "forceUser": "0",
                "username": self.username,
                "password": self.password
            }
            
            # Realizar la petición POST para login
            async with session.post(
                LOGIN_URL,
                data=form_data,
                allow_redirects=False  # No seguir redirecciones para poder capturar cookies
            ) as response:
                # Comprobar si el login fue exitoso (código 302 esperado)
                if response.status == 302:
                    # Guardar cookies de sesión
                    self.cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
                    log.info("✅ Login exitoso")
                    
                    # Mostrar las cookies obtenidas
                    for key, value in self.cookies.items():
                        log.debug(f"Cookie: {key}={value}")
                    
                    self.is_logged_in = True
                    return True
                else:
                    log.error(f"❌ Error en login. Status: {response.status}")
                    return False
        except Exception as e:
            log.error(f"❌ Error durante el login: {str(e)}")
            return False
        finally:
            # Cerrar la sesión si la creamos aquí
            if close_session:
                await session.close()
    
    # --------- INTERNAL ----------
    async def _get_pages(self, s) -> int:
        url = BASE + LIST.format(level_url=get_level_url(self.level), page=1, county=self.county_id, district=self.district_id, vacancy_type=self.vacancy_type)
        log.info(f"URL de búsqueda (page=1): {url}")
        try:
            async with s.get(url) as r:
                if r.status != 200:
                    log.warning(f"Error al obtener página de paginación: {r.status}")
                    return 1
                
                soup = BeautifulSoup(await r.text(), "html.parser")

            # Intento 1: Buscar el último elemento de la paginación
            pager = soup.select_one(".pagination li:last-child a[data-page]")
            if pager and pager.has_attr("data-page"):
                total = int(pager["data-page"])
                log.info(f"Total de páginas detectado: {total}")
                return total
                
            # Intento 2: Buscar todos los links de paginación y tomar el mayor
            pagination_links = soup.select(".pagination a[data-page]")
            if pagination_links:
                pages = [int(a["data-page"]) for a in pagination_links if a.has_attr("data-page")]
                if pages:
                    total = max(pages)
                    log.info(f"Total páginas (método alternativo): {total}")
                    return total
            
            # Si no se puede determinar, asumimos al menos 1 página
            log.warning("No se pudo determinar el número de páginas, usando 1")
            return 1
        except Exception as e:
            log.error(f"Error al obtener número de páginas: {str(e)}")
            # En caso de error, devolver un valor seguro
            return 1

    async def _extract_urls_from_page(self, s, page: int) -> List[Dict]:
        """
        Extrae ofertas básicas de una página específica, mejorando la extracción de URLs.
        
        Args:
            s: Sesión HTTP aiohttp
            page: Número de página a procesar
            
        Returns:
            Lista de ofertas básicas (sin detalle ni email)
        """
        url = BASE + LIST.format(level_url=get_level_url(self.level), page=page, county=self.county_id, district=self.district_id, vacancy_type=self.vacancy_type)
        log.info(f"URL de búsqueda (page={page}): {url}")
        try:
            # Usar cookies de sesión si estamos logueados
            cookies = self.cookies if self.is_logged_in else None
            async with self.sem, s.get(url, timeout=30, cookies=cookies) as r:
                if r.status != 200:
                    log.warning(f"Error al obtener página {page}: Status {r.status}")
                    return []
                html = await r.text()
                
            # Esperar un tiempo aleatorio para evitar ser bloqueados
            await rand_sleep(safe_mode=self.safe_mode)
            soup = BeautifulSoup(html, "html.parser")
            log.debug(f"Página {page}: HTML analizado correctamente ({len(html)} bytes)")
        except asyncio.TimeoutError:
            log.error(f"Timeout al obtener página {page}")
            return []
        except Exception as e:
            log.error(f"Error al procesar página {page}: {str(e)}")
            return []
        
        offers = []
        
        # --- Primero intentar con la tabla desktop ---
        tbl = soup.find("table", id="tblAdverts", class_="d-none d-lg-table")
        if tbl and tbl.tbody:
            log.info(f"Procesando tabla desktop para la página {page}")
            for tr in tbl.tbody.find_all("tr"):
                try:
                    tds = tr.find_all("td")
                    
                    # Extraer URL con manejo de errores mejorado
                    href = None
                    # Método 1: Usar data-href directamente de la fila
                    if tr.has_attr("data-href"):
                        href = tr["data-href"]
                        log.debug(f"Método 1: data-href en fila: {href}")
                    # Método 2: Buscar enlaces en la segunda columna (nombre de escuela)
                    elif len(tds) > 1:
                        links = tds[1].find_all("a")
                        if links:
                            href = links[0].get("href")
                            log.debug(f"Método 2: href en primer enlace: {href}")
                    
                    if not href:
                        log.warning(f"No se pudo extraer URL en fila de la página {page}")
                        continue
                    
                    # Asegurarse de que hay suficientes columnas
                    if len(tds) >= 6:
                        # Obtener el nombre de la escuela
                        school_name = tds[1].text.strip() if tds[1] else "Sin escuela"
                        # Obtener el tipo de vacante
                        vacancy_name = tds[2].text.strip() if tds[2] else ""
                        log.info(f"[DEBUG] Tipo de vacante extraído (columna 3): '{vacancy_name}' para escuela: '{school_name}'")
                        # Si vacancy_name está vacío, intenta buscar "Teacher" en el texto de la fila (para post-primary)
                        if not vacancy_name:
                            # Busca en todas las celdas si alguna contiene "Teacher"
                            for td in tds:
                                if "teacher" in td.text.lower():
                                    vacancy_name = "Teacher"
                                    break
                            # Si sigue vacío, busca en el texto completo de la fila
                            if not vacancy_name and "teacher" in tr.text.lower():
                                vacancy_name = "Teacher"
                        
                        # Filtrar colegios Gaelscoil
                        if "gaelscoil" in school_name.lower():
                            log.info(f"Filtrado colegio Gaelscoil: {school_name}")
                            continue
                        
                        # Filtrar vacantes según criterios
                        if not is_valid_vacancy(vacancy_name):
                            log.info(f"Filtrado vacante no compatible: {vacancy_name}")
                            continue
                            
                        # Crear oferta con todos los datos disponibles
                        offers.append({
                            "url": urljoin(BASE, href),
                            "id": tds[0].text.strip() if tds[0] else "Sin ID",
                            "school": school_name,
                            "vacancy": tds[2].text.strip() if tds[2] else "Sin vacante",
                            "status": tds[3].text.strip() if tds[3] else "Sin estado",
                            "county": tds[4].text.strip() if tds[4] else "Sin condado", 
                            "deadline": tds[5].text.strip() if tds[5] else "Sin fecha"
                        })
                    else:
                        log.warning(f"Fila con número insuficiente de columnas en página {page}: {len(tds)}")
                except Exception as e:
                    log.warning(f"Error procesando fila en tabla desktop, página {page}: {str(e)}")
                    # Seguir con la siguiente fila en caso de error
        
        # --- Si no se encontraron ofertas en la tabla desktop, intentar con la tabla móvil ---
        if not offers:
            log.info(f"No se encontraron ofertas en la tabla desktop, intentando con tabla móvil")
            mt = soup.select_one("table.mobileTable")
            if mt:
                log.info(f"Procesando tabla móvil para la página {page}")
                for tr in mt.find_all("tr"):
                    # Verificar si la fila tiene data-href
                    if not tr.has_attr("data-href"):
                        log.debug(f"Fila móvil sin data-href en página {page}")
                        continue
                        
                    try:
                        # Extraer URL y crear objeto base
                        href = urljoin(BASE, tr["data-href"])
                        data = {"url": href}
                        log.debug(f"URL extraída (móvil): {href}")
                        
                        # Extraer el ID si está disponible (a veces está en un elemento específico)
                        id_elem = tr.select_one(".advertId")
                        if id_elem:
                            data["id"] = id_elem.text.strip()
                        
                        # Buscar tarjeta principal
                        card = tr.find("td")
                        if not card:
                            continue
                        
                        # Extraer datos de la estructura móvil
                        for row in card.find_all("div", class_="mobileRow"):
                            lab = row.select_one(".mobileLabel")
                            val = row.select_one(".mobileData")
                            if not lab or not val:
                                continue
                                
                            # Mapear campos según su etiqueta
                            label_text = lab.text.strip().lower()
                            value_text = val.text.strip()
                            
                            if "school name" in label_text:
                                data["school"] = value_text
                            elif "type of vacancy" in label_text:
                                data["vacancy"] = value_text
                            elif "status" in label_text:
                                data["status"] = value_text
                            elif "county" in label_text:
                                data["county"] = value_text
                        
                        # Extraer fecha límite del encabezado
                        head = card.select_one(".headerData")
                        if head:
                            data["deadline"] = head.text.strip()
                            
                        # Filtrar colegios Gaelscoil
                        if "school" in data and "gaelscoil" in data["school"].lower():
                            log.info(f"Filtrado colegio Gaelscoil (móvil): {data.get('school')}")
                            continue
                        
                        # Filtrar vacantes según criterios
                        if "vacancy" in data and not is_valid_vacancy(data["vacancy"]):
                            log.info(f"Filtrado vacante no compatible (móvil): {data.get('vacancy')}")
                            continue
                            
                        offers.append(data)
                    except Exception as e:
                        log.warning(f"Error procesando fila móvil en página {page}: {str(e)}")
            else:
                log.warning("No se encontró ninguna tabla en la página %s", page)
        
        log.info(f"Total de {len(offers)} ofertas encontradas en página {page}")
        return offers

    async def _offer_detail(self, s, offer) -> Optional[Dict]:
        """
        Obtiene detalles adicionales y email de contacto de una oferta específica.
        
        Args:
            s: Sesión HTTP aiohttp
            offer: Diccionario con datos básicos de la oferta, incluyendo URL
            
        Returns:
            Diccionario con datos completos o None si no se pudo procesar
        """
        try:
            # Usar cookies de sesión si estamos logueados
            cookies = self.cookies if self.is_logged_in else None
            log.debug(f"Procesando detalles de oferta: {offer.get('url')}")
            
            async with self.sem, s.get(offer["url"], cookies=cookies, timeout=30) as r:
                if r.status != 200:
                    log.warning(f"Error al obtener detalles. Status: {r.status}")
                    return None
                html = await r.text()

            # Esperar un tiempo aleatorio para evitar ser bloqueados
            await rand_sleep(safe_mode=self.safe_mode)
            soup = BeautifulSoup(html, "html.parser")
            
            # Para debugging: guardar el HTML de la primera vacante
            if "🧪" in str(log.handlers):  # Solo para la prueba inicial
                try:
                    with open("debug_vacancy_page.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    log.debug("HTML de la vacante guardado en debug_vacancy_page.html para inspección")
                except Exception as e:
                    log.debug(f"No se pudo guardar HTML para debugging: {e}")
            
            # Buscar emails en estructura <div class="row advertRow"><div><strong>Apply To:</strong></div><div>EMAIL o texto con email</div></div>
            mail = None
            apply_to_email = None
            for row in soup.find_all('div', class_='row advertRow'):
                divs = row.find_all('div', recursive=False)
                if len(divs) >= 2:
                    label_div = divs[0]
                    value_div = divs[1]
                    # Buscar <strong> dentro del primer div
                    strong = label_div.find('strong')
                    label_text = strong.get_text(strip=True).lower().replace(':','') if strong else label_div.get_text(strip=True).lower().replace(':','')
                    log.info(f"[SCRAPER] Analizando fila: label='{label_text}', valor='{value_div.get_text(separator=' | ', strip=True)}'")
                    if 'apply to' in label_text:
                        # Buscar el primer email válido en todo el texto del value_div
                        value_text = value_div.get_text(separator=' ', strip=True)
                        possible_email = first_valid_email(value_text)
                        log.info(f"[SCRAPER] Buscando email en: {value_text}")
                        if possible_email and not any(bad in possible_email.lower() for bad in BAD_MAIL):
                            apply_to_email = possible_email
                            log.info(f"[SCRAPER] Email válido extraído: {apply_to_email}")
                            break
            # Si no se encontró email en Apply To, buscar en Enquiries To o Contact
            if not apply_to_email:
                for row in soup.find_all('div', class_='row advertRow'):
                    divs = row.find_all('div', recursive=False)
                    if len(divs) >= 2:
                        label_div = divs[0]
                        value_div = divs[1]
                        strong = label_div.find('strong')
                        label_text = strong.get_text(strip=True).lower().replace(':','') if strong else label_div.get_text(strip=True).lower().replace(':','')
                        if 'enquiries' in label_text or 'contact' in label_text:
                            value_text = value_div.get_text(separator=' ', strip=True)
                            possible_email = first_valid_email(value_text)
                            if possible_email and not any(bad in possible_email.lower() for bad in BAD_MAIL):
                                apply_to_email = possible_email
                                log.info(f"[SCRAPER] Email válido extraído de Enquiries/Contact: {apply_to_email}")
                                break
            # 2. Si no, buscar mailto junto a 'Apply to' (por compatibilidad con otros formatos)
            if not apply_to_email:
                for tag in soup.find_all(text=re.compile(r'apply to', re.I)):
                    parent = tag.parent
                    mailto_link = None
                    if parent and parent.find('a', href=re.compile(r'^mailto:', re.I)):
                        mailto_link = parent.find('a', href=re.compile(r'^mailto:', re.I))
                    elif parent and parent.find_next('a', href=re.compile(r'^mailto:', re.I)):
                        mailto_link = parent.find_next('a', href=re.compile(r'^mailto:', re.I))
                    if mailto_link:
                        email = mailto_link['href'][7:].split('?')[0].strip()
                        log.info(f"[SCRAPER] Encontrado mailto junto a 'Apply to': {email}")
                        if email and first_valid_email(email):
                            if not any(bad in email.lower() for bad in BAD_MAIL):
                                apply_to_email = email
                                log.info(f"[SCRAPER] Email válido extraído de mailto: {apply_to_email}")
                                break
            # Solo guardar el email si se encontró en Apply To
            if apply_to_email:
                mail = apply_to_email
                log.info(f"[SCRAPER] Email final guardado: {mail}")
            else:
                mail = None  # No guardar ningún otro email
                log.warning("[SCRAPER] No se encontró email en Apply To para esta oferta.")
            
            # 2. Extraer datos adicionales que solo están en la página de detalle
            try:
                # Buscar descripción completa - estrategia ampliada
                description_selectors = [
                    ".job-description", ".description", ".post-content", 
                    ".content", ".vacancy-description", "[class*='description']",
                    ".post-body", ".entry-content", ".main-content",
                    ".job-details", ".position-details", ".vacancy-details"
                ]
                description_text = None
                
                # Intentar selectores específicos primero
                for selector in description_selectors:
                    desc_elem = soup.select_one(selector)
                    if desc_elem:
                        description_text = desc_elem.get_text(strip=True, separator=" ")
                        if len(description_text) > 50:  # Solo si tiene contenido sustancial
                            offer["description"] = description_text[:800] + "..." if len(description_text) > 800 else description_text
                            log.debug(f"Descripción encontrada con selector: {selector}")
                            break
                
                # Si no se encuentra con selectores, buscar en el contenido principal
                if not description_text:
                    # Buscar el contenido principal de la página
                    main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|post"))
                    if main_content:
                        # Extraer párrafos que contengan información sustancial
                        paragraphs = main_content.find_all("p")
                        content_paragraphs = []
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if len(text) > 30 and not any(skip in text.lower() for skip in ['cookie', 'privacy', 'copyright']):
                                content_paragraphs.append(text)
                        
                        if content_paragraphs:
                            description_text = ' '.join(content_paragraphs[:3])  # Primeros 3 párrafos
                            offer["description"] = description_text[:800] + "..." if len(description_text) > 800 else description_text
                            log.debug("Descripción extraída del contenido principal")
                
                # Buscar información específica del puesto
                position_info = {}
                
                # Buscar salario
                salary_patterns = [
                    r'salary[:\s]*[€£$]?[\d,]+[-\s]*[€£$]?[\d,]*',
                    r'[€£$][\d,]+\s*(?:per|/)\s*(?:year|annum|hour)',
                    r'scale[:\s]*\w+',
                    r'pay[:\s]*[€£$]?[\d,]+'
                ]
                full_text = soup.get_text()
                for pattern in salary_patterns:
                    salary_match = re.search(pattern, full_text, re.IGNORECASE)
                    if salary_match:
                        position_info["salary"] = salary_match.group(0).strip()
                        break
                
                # Buscar horario de trabajo
                schedule_patterns = [
                    r'(?:full|part)[-\s]*time',
                    r'\d+\s*hours?\s*per\s*week',
                    r'temporary|permanent|contract',
                    r'maternity\s*cover',
                    r'fixed[- ]term'
                ]
                for pattern in schedule_patterns:
                    schedule_match = re.search(pattern, full_text, re.IGNORECASE)
                    if schedule_match:
                        position_info["schedule"] = schedule_match.group(0).strip()
                        break
                
                if position_info:
                    offer["position_info"] = position_info
                
                # Buscar requisitos y APPLICATION REQUIREMENTS - estrategia mejorada
                requirements_selectors = [
                    ".requirements", ".application-requirements", "[class*='requirement']",
                    ".qualifications", ".criteria", ".essential", ".desirable",
                    ".application", ".apply", ".conditions", ".advertRow"
                ]
                requirements_text = None
                
                # Primero buscar específicamente la estructura advertRow
                advert_rows = soup.find_all("div", class_="advertRow")
                if advert_rows:
                    log.debug(f"Encontradas {len(advert_rows)} filas advertRow")
                    for row in advert_rows:
                        # Buscar listas dentro de la fila
                        lists = row.find_all(["ul", "ol"])
                        if lists:
                            list_content = []
                            for ul in lists:
                                items = ul.find_all("li")
                                for li in items:
                                    item_text = li.get_text(strip=True)
                                    if item_text:
                                        list_content.append(f"• {item_text}")
                            
                            if list_content:
                                requirements_text = ' '.join(list_content)
                                offer["requirements"] = requirements_text[:400] + "..." if len(requirements_text) > 400 else requirements_text
                                log.debug(f"Requisitos encontrados en advertRow: {requirements_text[:100]}...")
                                break
                
                # Si no se encontró en advertRow, intentar con selectores CSS tradicionales
                if not requirements_text:
                    for selector in requirements_selectors:
                        req_elem = soup.select_one(selector)
                        if req_elem:
                            requirements_text = req_elem.get_text(strip=True, separator=" ")
                            if len(requirements_text) > 20:
                                offer["requirements"] = requirements_text[:300] + "..." if len(requirements_text) > 300 else requirements_text
                                log.debug(f"Requisitos encontrados con selector: {selector}")
                                break
                
                # Si no se encontraron con selectores, buscar por texto
                if not requirements_text:
                    log.debug("No se encontraron requisitos con selectores, buscando por texto...")
                    
                    # Buscar en todo el texto de la página
                    full_text = soup.get_text()
                    
                    # Buscar palabras clave de requisitos
                    requirement_keywords = [
                        'application requirements', 'requirements', 'qualifications', 
                        'essential criteria', 'desirable criteria', 'criteria',
                        'must have', 'should have', 'experience required',
                        'qualification required', 'essential', 'desirable',
                        'letter of application', 'application form'
                    ]
                    
                    # Buscar encabezados que contengan estas palabras
                    requirement_headings = soup.find_all(lambda tag: tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'p'] 
                                                       and tag.text and any(keyword in tag.text.lower() 
                                                       for keyword in requirement_keywords))
                    
                    log.debug(f"Encontrados {len(requirement_headings)} posibles encabezados de requisitos")
                    
                    for heading in requirement_headings:
                        log.debug(f"Analizando encabezado: {heading.text[:100]}...")
                        
                        # Buscar el contenido después del encabezado
                        next_content = []
                        current = heading.next_sibling
                        
                        # También intentar buscar en el siguiente elemento hermano
                        if not current:
                            parent = heading.parent
                            if parent:
                                next_elem = parent.find_next_sibling()
                                if next_elem:
                                    current = next_elem
                        
                        while current and len(' '.join(next_content)) < 500:
                            if hasattr(current, 'get_text'):
                                text = current.get_text(strip=True)
                                if text and len(text) > 10:  # Solo texto sustancial
                                    next_content.append(text)
                                    # Si encontramos una lista de elementos, es probable que sean requisitos
                                    if any(indicator in text.lower() for indicator in ['•', '-', '1.', '2.', 'degree', 'experience', 'qualification']):
                                        break
                            elif isinstance(current, str) and current.strip():
                                next_content.append(current.strip())
                            current = current.next_sibling
                            
                        if next_content:
                            requirements_text = ' '.join(next_content)
                            offer["requirements"] = requirements_text[:400] + "..." if len(requirements_text) > 400 else requirements_text
                            log.debug(f"Requisitos encontrados después del encabezado: {heading.text[:50]}...")
                            log.debug(f"Contenido extraído: {requirements_text[:100]}...")
                            break
                
                # Último intento: buscar patrones específicos en el texto completo
                if not requirements_text:
                    log.debug("Último intento: buscando patrones en texto completo...")
                    
                    # Buscar secciones que contengan listas de requisitos
                    text_lines = full_text.split('\n')
                    in_requirements_section = False
                    requirements_lines = []
                    
                    for line in text_lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Detectar inicio de sección de requisitos
                        if any(keyword in line.lower() for keyword in ['application requirements', 'requirements:', 'qualifications:', 'essential:', 'letter of application']):
                            in_requirements_section = True
                            requirements_lines = [line]
                            continue
                            
                        # Si estamos en la sección de requisitos
                        if in_requirements_section:
                            # Continuar hasta encontrar una nueva sección o fin
                            if (line.startswith(('HOW TO APPLY', 'CONTACT', 'SALARY', 'CLOSING DATE')) or 
                                len(requirements_lines) > 10):  # Limitar tamaño
                                break
                            requirements_lines.append(line)
                    
                    if requirements_lines and len(requirements_lines) > 1:
                        requirements_text = ' '.join(requirements_lines)
                        offer["requirements"] = requirements_text[:400] + "..." if len(requirements_text) > 400 else requirements_text
                        log.debug(f"Requisitos encontrados en texto completo: {requirements_text[:100]}...")
                
                if not requirements_text:
                    log.debug("No se pudieron encontrar requisitos con ningún método")
                else:
                    log.debug(f"✅ Requisitos extraídos: {requirements_text[:50]}...")
                
                # Log de otros datos extraídos
                if offer.get("description"):
                    log.debug(f"✅ Descripción extraída: {offer['description'][:50]}...")
                if offer.get("contact_info"):
                    log.debug(f"✅ Contacto extraído: {offer['contact_info'][:50]}...")
                if offer.get("position_info"):
                    log.debug(f"✅ Info posición: {list(offer['position_info'].keys())}")
                if offer.get("posted"):
                    log.debug(f"✅ Fecha publicación: {offer['posted']}")
                if offer.get("closing_date"):
                    log.debug(f"✅ Fecha cierre: {offer['closing_date']}")
                
                # Buscar fecha de publicación - varios selectores posibles
                date_selectors = [
                    ".post-date", ".date", ".published", ".created",
                    "[class*='date']", ".meta-date", ".publish-date"
                ]
                for selector in date_selectors:
                    date_elem = soup.select_one(selector)
                    if date_elem:
                        date_text = date_elem.text.strip()
                        if date_text and len(date_text) > 3:  # Asegurar que hay contenido
                            offer["posted"] = date_text
                            log.debug(f"Fecha encontrada con selector: {selector}")
                            break
                
                # Buscar fecha de cierre también en el texto
                if not offer.get("posted"):
                    closing_patterns = [
                        r'closing\s+date[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                        r'apply\s+by[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                        r'deadline[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})'
                    ]
                    for pattern in closing_patterns:
                        date_match = re.search(pattern, full_text, re.IGNORECASE)
                        if date_match:
                            offer["closing_date"] = date_match.group(1).strip()
                            break
                
                # Buscar información de contacto - varios selectores posibles
                contact_selectors = [
                    ".contact-info", ".contact", ".contact-details",
                    "[class*='contact']", ".principal", ".school-contact"
                ]
                for selector in contact_selectors:
                    contact_elem = soup.select_one(selector)
                    if contact_elem:
                        contact_text = contact_elem.text.strip()
                        if contact_text and len(contact_text) > 5:
                            offer["contact_info"] = contact_text
                            log.debug(f"Contacto encontrado con selector: {selector}")
                            break
                
                # Buscar más información de contacto en el texto
                if not offer.get("contact_info"):
                    contact_patterns = [
                        r'contact[:\s]*([^\n]+)',
                        r'principal[:\s]*([^\n]+)',
                        r'queries[:\s]*([^\n]+)',
                        r'further\s+information[:\s]*([^\n]+)'
                    ]
                    for pattern in contact_patterns:
                        contact_match = re.search(pattern, full_text, re.IGNORECASE)
                        if contact_match:
                            contact_text = contact_match.group(1).strip()
                            if len(contact_text) > 10:
                                offer["contact_info"] = contact_text[:200]
                                break
                
                # Buscar información adicional en metadatos o elementos estructurados
                meta_info = {}
                
                # Buscar elementos con etiquetas como "School:", "Position:", etc.
                labels = soup.find_all(lambda tag: tag.text and ':' in tag.text and len(tag.text) < 50)
                for label in labels:
                    label_text = label.text.strip().lower()
                    if any(keyword in label_text for keyword in ['school', 'position', 'location', 'salary', 'hours']):
                        # Buscar el valor después de la etiqueta
                        next_elem = label.next_sibling
                        if next_elem and hasattr(next_elem, 'text'):
                            meta_info[label_text] = next_elem.text.strip()
                
                if meta_info:
                    offer["additional_info"] = meta_info
                    log.debug(f"Información adicional encontrada: {list(meta_info.keys())}")
                
                # Buscar el roll number específicamente
                roll_number_patterns = [
                    r'roll\s*(?:number|no)[:.]?\s*([\d\w]+)',
                    r'roll\s*(?:number|no)[:.]\s*([\d\w]+)',
                    r'roll\s*(?:number|no)\s*(?:is|=)\s*([\d\w]+)',
                    r'school\s*roll\s*(?:number|no)[:.]\s*([\d\w]+)',
                    r'(\d{5}[A-Z])'  # Patrón típico de roll number irlandés: 5 dígitos y una letra
                ]
                
                for pattern in roll_number_patterns:
                    roll_match = re.search(pattern, full_text, re.IGNORECASE)
                    if roll_match:
                        roll_number = roll_match.group(1).strip()
                        offer["roll_number"] = roll_number
                        log.info(f"Roll number encontrado: {roll_number}")
                        break
                
                # Si no se encontró con regex, buscar en las tablas de información de la escuela
                if not offer.get("roll_number"):
                    tables = soup.find_all("table")
                    for table in tables:
                        rows = table.find_all("tr")
                        for row in rows:
                            cells = row.find_all(["td", "th"])
                            if len(cells) >= 2:
                                header_text = cells[0].text.strip().lower()
                                if "roll" in header_text and ("number" in header_text or "no" in header_text):
                                    value_text = cells[1].text.strip()
                                    if value_text:
                                        offer["roll_number"] = value_text
                                        log.info(f"Roll number encontrado en tabla: {value_text}")
                                        break
                        if offer.get("roll_number"):
                            break
                
                # Buscar en divs con estructura de datos clave-valor
                if not offer.get("roll_number"):
                    key_value_divs = soup.select("div.key-value, div.field, div.info-row, div.school-info")
                    for div in key_value_divs:
                        div_text = div.text.lower()
                        if "roll" in div_text and ("number" in div_text or "no" in div_text):
                            # Buscar el valor después del texto "roll number"
                            match = re.search(r'roll\s*(?:number|no)[:\s]*([^\s]+)', div_text)
                            if match:
                                roll_number = match.group(1).strip()
                                offer["roll_number"] = roll_number
                                log.info(f"Roll number encontrado en div: {roll_number}")
                                break
                
                # Si aún no se ha encontrado el roll number, intentar extraerlo del título o descripción
                if not offer.get("roll_number"):
                    # Intentar una búsqueda más amplia en el contenido
                    school_name = offer.get("school_name", "")
                    if school_name:
                        # Buscar páginas web conocidas de directorios escolares para este colegio
                        log.debug(f"No se pudo encontrar roll number en la página. Se usará 'N/A' como valor predeterminado.")
                
            except Exception as e:
                log.warning(f"Error al extraer datos adicionales: {str(e)}")

            # 3. Si no se encontró email en la página principal, buscar en enlaces de contacto
            if not mail:
                log.debug("Email no encontrado en página principal, buscando en enlaces de contacto")
                # Encontrar enlaces potenciales que podrían contener información de contacto
                links = [a["href"] for a in soup("a", href=True)
                         if any(k in a["href"].lower() for k in ("contact", "about", "staff"))][:2]
                
                for link in links:
                    try:
                        full_url = urljoin(offer["url"], link)
                        log.debug(f"Buscando email en: {full_url}")
                        
                        # Usar cookies de sesión si estamos logueados
                        cookies = self.cookies if self.is_logged_in else None
                        async with self.sem, s.get(full_url, cookies=cookies, timeout=30) as r2:
                            if r2.status == 200:
                                sub = await r2.text()
                                if m := first_valid_email(sub):
                                    mail = m
                                    log.debug(f"Email encontrado en enlace secundario: {mail}")
                                    break
                            else:
                                log.debug(f"Error al acceder a enlace secundario. Status: {r2.status}")
                    except Exception as e:
                        log.warning(f"Error al procesar enlace secundario: {str(e)}")
                    
                    await rand_sleep(safe_mode=self.safe_mode)

            # 4. Añadir email si se encontró - PERO SIEMPRE DEVOLVER EL RESULTADO CON TODA LA INFO
            if mail:
                offer["email"] = mail
            else:
                log.debug(f"No se encontró email para la oferta: {offer.get('school', 'Sin escuela')}")
                # NO devolver None - siempre devolver la información completa aunque no haya email
            
            # Log de información completa extraída (incluyendo requirements completos)
            title = f"{offer.get('school', 'N/A')} - {offer.get('vacancy', 'N/A')}"
            requirements_text = offer.get('requirements', '')
            description = offer.get('description', '')
            contact_info = offer.get('contact_info', '')
            emails = [offer.get('email')] if offer.get('email') else []
            
            log.info(f"\n=== OFERTA PROCESADA ===")
            log.info(f"URL: {offer.get('url', 'N/A')}")
            log.info(f"TÍTULO: {title}")
            
            # Mostrar requirements completos (no truncados)
            if requirements_text:
                log.info(f"\nAPPLICATION REQUIREMENTS COMPLETOS:")
                log.info(f"{requirements_text}")
            else:
                log.info("APPLICATION REQUIREMENTS: No encontrados")
            
            # Mostrar emails
            if emails and emails[0]:
                log.info(f"\nEMAILS ENCONTRADOS: {', '.join(emails)}")
            else:
                log.info("EMAILS: No encontrados")
            
            log.info(f"CONTACT INFO: {contact_info}")
            log.info(f"DESCRIPTION (primeros 200 chars): {description[:200]}{'...' if len(description) > 200 else ''}")
            log.info(f"========================\n")
            
            # Si vacancy está vacío, intenta extraerlo del h2 principal
            if not offer.get('vacancy') or offer.get('vacancy', '').strip() == '':
                h2 = soup.select_one('div.purple-text.col-8 h2')
                if h2 and h2.text.strip():
                    offer['vacancy'] = h2.text.strip()
                    log.info(f"[SCRAPER] Tipo de vacante extraído de h2: {offer['vacancy']}")
            
            # Siempre devolver la oferta con toda la información extraída
            return offer
                
        except asyncio.TimeoutError:
            log.warning(f"Timeout al obtener detalles de: {offer.get('url')}")
            return None
        except Exception as e:
            log.warning(f"Error al procesar detalles: {str(e)}")
            return None

    # Método para validar ID de distrito
    def validate_district_id(self, district_id):
        """
        Valida que el ID de distrito proporcionado sea válido.
        
        Args:
            district_id: ID del distrito a validar
            
        Returns:
            bool: True si el ID es válido, False en caso contrario
        """
        # Si es vacío, se considera válido (todo Dublin)
        if not district_id:
            return True
            
        # Verificar si está en el diccionario de distritos
        if district_id in DUBLIN_DISTRICTS:
            log.info(f"Distrito válido: {district_id} ({DUBLIN_DISTRICTS.get(district_id)})")
            return True
        
        log.warning(f"ID de distrito no válido: {district_id}")
        return False

    def prepare_offer_data_for_application_form(self, offer: Dict) -> Dict:
        """
        Prepara los datos de una oferta para personalizar un application form.
        
        Args:
            offer: Diccionario con los datos de la oferta
            
        Returns:
            Diccionario con los datos formateados para el application form
        """
        # Extraer y mostrar todas las claves disponibles para depuración
        log.info(f"📊 Claves disponibles en la oferta: {list(offer.keys())}")
        
        # Extraer datos necesarios con verificación detallada
        position = None
        if 'vacancy' in offer:
            position = offer['vacancy']
            log.info(f"✅ Usando 'vacancy' como posición: {position}")
        elif 'position' in offer:
            position = offer['position']
            log.info(f"✅ Usando 'position' como posición: {position}")
        else:
            position = 'Teaching Position'
            log.warning(f"⚠️ No se encontró campo de posición, usando valor predeterminado: {position}")
            
        school_name = None
        if 'school' in offer:
            school_name = offer['school']
            log.info(f"✅ Usando 'school' como nombre de escuela: {school_name}")
        elif 'school_name' in offer:
            school_name = offer['school_name']
            log.info(f"✅ Usando 'school_name' como nombre de escuela: {school_name}")
        else:
            school_name = 'School'
            log.warning(f"⚠️ No se encontró campo de escuela, usando valor predeterminado: {school_name}")
            
        roll_number = None
        if 'roll_number' in offer:
            roll_number = offer['roll_number']
            # Limpiar el roll number para quitar texto adicional como "Apply"
            if roll_number and isinstance(roll_number, str):
                if "Apply" in roll_number:
                    clean_roll_number = roll_number.split("Apply")[0].strip()
                    log.info(f"Roll Number limpiado: '{roll_number}' -> '{clean_roll_number}'")
                    roll_number = clean_roll_number
            log.info(f"✅ Usando roll number: {roll_number}")
        else:
            roll_number = 'N/A'
            log.warning(f"⚠️ No se encontró roll number, usando valor predeterminado: {roll_number}")
        
        log.info(f"📝 Preparando datos para application form:")
        log.info(f"   • Posición: {position}")
        log.info(f"   • Escuela: {school_name}")
        log.info(f"   • Roll Number: {roll_number}")
        
        # Datos para personalizar el formulario
        return {
            'position': position,
            'school_name': school_name,
            'roll_number': roll_number
        }
    
    async def test_application_forms(self, template_path: str) -> List[str]:
        """
        Genera application forms personalizados para 10 vacantes de prueba.
        
        Args:
            template_path: Ruta a la plantilla del application form en formato .docx
            
        Returns:
            Lista con las rutas a los application forms personalizados
        """
        from src.utils.document_reader import DocumentReader
        import os
        from datetime import datetime
        import random
        
        # Crear datos de prueba para 10 vacantes ficticias
        test_vacancies = [
            {
                "vacancy": "Mainstream Class Teacher",
                "school": "Grace Park ETNS",
                "roll_number": "20486R"
            },
            {
                "vacancy": "Special Education Teacher",
                "school": "St. Patrick's National School",
                "roll_number": "18734W"
            },
            {
                "vacancy": "Resource Teacher",
                "school": "Holy Family Junior School",
                "roll_number": "19876Q"
            },
            {
                "vacancy": "Classroom Teacher",
                "school": "Dublin South Central ETNS",
                "roll_number": "20537P"
            },
            {
                "vacancy": "EAL Teacher",
                "school": "Scoil Chormaic CNS",
                "roll_number": "20269Y"
            },
            {
                "vacancy": "ASD Class Teacher",
                "school": "Our Lady of Mercy National School",
                "roll_number": "17405T"
            },
            {
                "vacancy": "SET Teacher",
                "school": "Gaelscoil na Camóige",
                "roll_number": "19991V"
            },
            {
                "vacancy": "Learning Support Teacher",
                "school": "St. Mary's Primary School",
                "roll_number": "20123E"
            },
            {
                "vacancy": "Primary School Teacher",
                "school": "Bunscoil Ballincurrig",
                "roll_number": "18544N"
            },
            {
                "vacancy": "Class Teacher - 3rd Class",
                "school": "St. Joseph's Catholic NS",
                "roll_number": "19345K"
            }
        ]
        
        log.info(f"🧪 Generando application forms de prueba para 10 vacantes ficticias...")
        
        if not os.path.exists(template_path):
            log.error(f"❌ No se encontró la plantilla de application form: {template_path}")
            return []
            
        if not template_path.lower().endswith('.docx'):
            log.error(f"❌ La plantilla de application form debe ser un archivo .docx: {template_path}")
            return []
            
        # Crear carpeta temporal para los archivos personalizados si no existe
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Timestamp para evitar sobreescrituras
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        document_reader = DocumentReader()
        generated_forms = []
        
        for i, vacancy in enumerate(test_vacancies):
            try:
                # Preparar datos para personalización
                offer_data = self.prepare_offer_data_for_application_form(vacancy)
                
                # Añadir un número aleatorio a la vacante para simular más variedad
                school_name = vacancy["school"]
                log.info(f"📝 Personalizando application form para: {school_name} - {vacancy['vacancy']}")
                
                # Nombre del archivo personalizado
                school_name_safe = ''.join(c if c.isalnum() else '_' for c in school_name)
                custom_filename = f"Test_Application_Form_{school_name_safe}_{timestamp}_{i}.docx"
                output_path = os.path.join(temp_dir, custom_filename)
                
                # Personalizar el documento
                custom_path = document_reader.customize_application_form_pdf(
                    template_path=template_path,
                    output_path=output_path,
                    offer_data=offer_data
                )
                
                if custom_path:
                    generated_forms.append(custom_path)
                    log.info(f"✅ Application form de prueba generado: {custom_path}")
                else:
                    log.warning(f"⚠️ No se pudo personalizar el application form para: {school_name}")
                
            except Exception as e:
                log.error(f"❌ Error al personalizar application form: {str(e)}")
        
        log.info(f"✅ Generados {len(generated_forms)} application forms de prueba")
        return generated_forms

# ---------------- EJEMPLO DE USO ----------------
async def run():
    """
    Ejemplo de uso del scraper
    """
    # Obtener credenciales desde variables de entorno o establecerlas directamente
    username = os.getenv("EDUCATIONPOSTS_USERNAME")
    password = os.getenv("EDUCATIONPOSTS_PASSWORD")
    
    if not username or not password:
        # Si no hay credenciales en variables de entorno, usar valores por defecto
        username = "sonia.valencia.sonia@gmail.com"  # Reemplaza con tu usuario real o usa None
        password = "Irlanda-2022"                    # Reemplaza con tu contraseña real o usa None
    
    # Crear instancia del scraper con credenciales
    # county_id = ""  → todos | 4 → Cork | 27 → Dublin…
    scraper = EducationPosts(
        level="primary", 
        county_id="",  # Todos los condados
        max_workers=1,  # Reducido para evitar detección
        safe_mode=True,  # Activar modo seguro
        username=username,
        password=password
    )
    
    # Ejecutar el scraping con login previo - SIN LÍMITE DE PÁGINAS
    data = await scraper.fetch_all(max_pages=None, login_first=True)
    
    # Mostrar algunos resultados
    print(f"\nSe encontraron {len(data)} ofertas con email")
    for i, o in enumerate(data[:3], 1):
        print(f"\n--- OFERTA {i} ---")
        print(f"Escuela: {o.get('school', 'N/A')}")
        print(f"Vacante: {o.get('vacancy', 'N/A')}")
        print(f"Email: {o.get('email', 'N/A')}")
        print(f"URL: {o.get('url', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(run())

# Mapeo de distritos de Dublin por ID (basado en el parámetro pd)
DUBLIN_DISTRICTS = {
    "": "Todo Dublin", # pd vacío = todo Dublin
    "1": "Dublin 1",   # Código 1 = Dublin 1
    "2": "Dublin 2",   # Código 2 = Dublin 2
    "3": "Dublin 3",   # Código 3 = Dublin 3
    "4": "Dublin 4",   # Código 4 = Dublin 4
    "5": "Dublin 5",   # Código 5 = Dublin 5
    "6": "Dublin 6",   # Código 6 = Dublin 6
    "7": "Dublin 6W",  # Código 7 = Dublin 6W
    "8": "Dublin 7",   # Código 8 = Dublin 7
    "9": "Dublin 8",   # Código 9 = Dublin 8
    "10": "Dublin 9",  # Código 10 = Dublin 9
    "11": "Dublin 10", # Código 11 = Dublin 10
    "12": "Dublin 11", # Código 12 = Dublin 11
    "13": "Dublin 12", # Código 13 = Dublin 12
    "14": "Dublin 13", # Código 14 = Dublin 13
    "15": "Dublin 14", # Código 15 = Dublin 14
    "16": "Dublin 15", # Código 16 = Dublin 15
    "17": "Dublin 16", # Código 17 = Dublin 16
    "18": "Dublin 17", # Código 18 = Dublin 17
    "19": "Dublin 18", # Código 19 = Dublin 18
    "20": "Dublin 20", # Código 20 = Dublin 20
    "21": "Dublin 22", # Código 21 = Dublin 22
    "22": "Dublin 24"  # Código 22 = Dublin 24
}
# Agrupación de distritos por zonas geográficas
# Los distritos se mapean a sus códigos reales en la API
DUBLIN_ZONES = {
    "1": ["1"],
    "2": ["2"],
    "3": ["3"],
    "4": ["4"],
    "5": ["5"],
    "6": ["6"],
    "6w": ["7"],   # Dublin 6W usa el código 7
    "7": ["8"],    # Dublin 7 usa el código 8
    "8": ["9"],    # Dublin 8 usa el código 9
    "9": ["10"],   # Dublin 9 usa el código 10
    "10": ["11"],  # Dublin 10 usa el código 11
    "11": ["12"],  # Dublin 11 usa el código 12
    "12": ["13"],  # Dublin 12 usa el código 13
    "13": ["14"],  # Dublin 13 usa el código 14
    "14": ["15"],  # Dublin 14 usa el código 15
    "15": ["16"],  # Dublin 15 usa el código 16
    "16": ["17"],  # Dublin 16 usa el código 17
    "17": ["18"],  # Dublin 17 usa el código 18
    "18": ["19"],  # Dublin 18 usa el código 19
    "20": ["20"],  # Dublin 20 usa el código 20
    "22": ["21"],  # Dublin 22 usa el código 21
    "24": ["22"],  # Dublin 24 usa el código 22
    "all": ""      # Todo Dublin
}
