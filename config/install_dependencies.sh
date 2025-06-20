#!/bin/bash

echo "🚀 Instalador de dependencias para ScrapingProfesNomadas"
echo "=" * 50

# Verificar si estamos en el directorio correcto
if [ ! -f "telegram_bot.py" ]; then
    echo "❌ Error: Ejecuta este script desde el directorio del proyecto"
    exit 1
fi

echo "📦 Instalando dependencias básicas..."

# Instalar dependencias básicas para el bot
pip3 install python-telegram-bot==20.8 python-dotenv==1.0.0 aiofiles==23.2.1

# Verificar instalación
echo "🧪 Verificando instalación..."

python3 -c "
import sys
print(f'✅ Python {sys.version}')

try:
    import telegram
    print('✅ python-telegram-bot instalado')
except ImportError:
    print('❌ python-telegram-bot NO instalado')

try:
    from dotenv import load_dotenv
    print('✅ python-dotenv instalado')
except ImportError:
    print('❌ python-dotenv NO instalado')

try:
    import aiofiles
    print('✅ aiofiles instalado')
except ImportError:
    print('❌ aiofiles NO instalado')
"

echo ""
echo "✅ Instalación completada"
echo "💡 Ahora puedes ejecutar: python3 test_system.py"
