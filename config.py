"""
Configuración centralizada del proyecto
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Rutas del proyecto
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'templates')
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')

# Configuración de logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
LOG_FILE = os.path.join(LOGS_DIR, 'scraping_agent.log')

# Configuración de la aplicación
DEFAULT_EMAIL_TEMPLATE = os.path.join(TEMPLATES_DIR, 'email_template.txt')
EXCEL_TEMPLATE = os.path.join(DATA_DIR, 'practicasPlantilla.xlsx')
CONTACTOS_FILE = os.path.join(DATA_DIR, 'Contactos de Referentes.xlsx')

# Variables de entorno requeridas
REQUIRED_ENV_VARS = [
    'TELEGRAM_BOT_TOKEN',
    'OPENAI_API_KEY',
    'EMAIL_HOST',
    'EMAIL_PORT',
    'EMAIL_USER',
    'EMAIL_PASSWORD'
]

def validate_environment():
    """Valida que todas las variables de entorno requeridas estén configuradas"""
    missing_vars = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise EnvironmentError(
            f"Variables de entorno faltantes: {', '.join(missing_vars)}\n"
            f"Por favor, configura estas variables en tu archivo .env"
        )
    
    return True
