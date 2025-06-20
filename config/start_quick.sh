#!/bin/bash

# Script de inicio rápido para ScrapingProfesNomadas
# Este script configura e inicia el sistema automáticamente

echo "🎓 ScrapingProfesNomadas - Inicio Rápido"
echo "======================================="

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no está instalado"
    echo "💡 Instala Python 3.8+ desde https://python.org"
    exit 1
fi

echo "✅ Python 3 detectado: $(python3 --version)"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar entorno virtual
echo "🚀 Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
echo "⬆️ Actualizando pip..."
pip install --upgrade pip --quiet

# Instalar dependencias básicas
echo "📚 Instalando dependencias básicas..."
pip install requests beautifulsoup4 python-telegram-bot python-dotenv lxml --quiet

# Verificar archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️ Archivo .env no encontrado"
    echo "📄 Creando archivo .env desde template..."
    
    cat > .env << 'EOF'
# Configuración de ScrapingProfesNomadas

# Bot de Telegram (OBLIGATORIO)
TELEGRAM_BOT_TOKEN=

# APIs de IA (OPCIONAL - para emails más personalizados)
AI_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Configuración de scraping
MAX_PAGES=3
DELAY_BETWEEN_REQUESTS=2
LOG_LEVEL=INFO
EOF

    echo "✅ Archivo .env creado"
    echo ""
    echo "🔧 CONFIGURACIÓN REQUERIDA:"
    echo "1. Edita el archivo .env"
    echo "2. Añade tu TELEGRAM_BOT_TOKEN"
    echo "3. Opcionalmente añade claves de IA"
    echo ""
    echo "Para obtener token de Telegram:"
    echo "• Contacta @BotFather en Telegram"
    echo "• Ejecuta /newbot"
    echo "• Copia el token al archivo .env"
    echo ""
    read -p "Presiona Enter después de configurar .env..."
fi

# Verificar token de Telegram
if ! grep -q "TELEGRAM_BOT_TOKEN=.*[^[:space:]]" .env; then
    echo "❌ TELEGRAM_BOT_TOKEN no configurado en .env"
    echo "💡 Edita .env y añade tu token de Telegram"
    exit 1
fi

echo "✅ Token de Telegram configurado"

# Intentar instalar dependencias opcionales
echo "📊 Instalando dependencias opcionales..."
pip install pandas openpyxl openai anthropic --quiet 2>/dev/null || echo "⚠️ Algunas dependencias opcionales no se instalaron"

# Ejecutar prueba rápida
echo "🧪 Ejecutando prueba rápida del sistema..."
python3 test_quick.py

# Preguntar si iniciar el bot
echo ""
echo "🤖 ¿Quieres iniciar el bot de Telegram ahora? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "🚀 Iniciando ScrapingProfesNomadas..."
    echo "📱 Busca tu bot en Telegram y envía /start"
    echo "🛑 Para detener: Ctrl+C"
    echo ""
    python3 main.py
else
    echo "👍 Sistema configurado correctamente"
    echo ""
    echo "Para iniciar el bot manualmente:"
    echo "  source venv/bin/activate"
    echo "  python3 main.py"
    echo ""
    echo "Para generar template Excel:"
    echo "  python3 generate_excel_template.py"
    echo ""
    echo "Para ejecutar pruebas:"
    echo "  python3 test_quick.py"
fi
