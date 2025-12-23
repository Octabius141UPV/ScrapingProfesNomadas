#!/usr/bin/env python3
"""
Script para inicializar la base de datos CRM en Notion.
Crea la estructura necesaria o verifica que existe.
"""
import os
import sys
from dotenv import load_dotenv

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv(override=True)

from src.utils.notion_crm_manager import NotionCRMManager, create_notion_database_schema


def print_setup_instructions():
    """Imprime las instrucciones para configurar Notion CRM."""
    print("\n" + "="*70)
    print("INSTRUCCIONES PARA CONFIGURAR NOTION CRM")
    print("="*70)
    print("\n📋 Paso 1: Crear una integración en Notion")
    print("   1. Ve a https://www.notion.so/my-integrations")
    print("   2. Haz clic en '+ New integration'")
    print("   3. Dale un nombre (ej: 'Profes Nómadas CRM')")
    print("   4. Selecciona el workspace donde quieres crear la base de datos")
    print("   5. Configura los permisos:")
    print("      - Read content: ✓")
    print("      - Update content: ✓")
    print("      - Insert content: ✓")
    print("   6. Copia el 'Internal Integration Token' (comienza con 'secret_')")
    print("   7. Añádelo a tu .env como NOTION_API_KEY\n")
    
    print("📊 Paso 2: Crear la base de datos en Notion")
    print("   1. Ve a tu workspace de Notion")
    print("   2. Crea una nueva página (ej: 'Schools CRM')")
    print("   3. Dentro de esa página, crea una base de datos 'Table - Full page'")
    print("   4. Configura las siguientes propiedades:\n")
    
    schema = create_notion_database_schema()
    for prop_name, prop_config in schema.items():
        prop_type = prop_config['type']
        print(f"      • {prop_name} ({prop_type})")
        if 'options' in prop_config:
            options = ', '.join(prop_config['options'])
            print(f"        Opciones: {options}")
    
    print("\n🔗 Paso 3: Conectar la integración a la base de datos")
    print("   1. Abre la página con tu base de datos en Notion")
    print("   2. Haz clic en '...' (tres puntos) en la esquina superior derecha")
    print("   3. Ve a 'Add connections'")
    print("   4. Busca y selecciona tu integración 'Profes Nómadas CRM'")
    print("   5. Copia el ID de la base de datos de la URL:")
    print("      URL: https://notion.so/workspace/DATABASE_ID?v=...")
    print("      Copia solo el DATABASE_ID (32 caracteres alfanuméricos)")
    print("   6. Añádelo a tu .env como NOTION_DATABASE_ID\n")
    
    print("✅ Paso 4: Verificar la configuración")
    print("   Ejecuta nuevamente este script para verificar que todo funciona\n")
    print("="*70 + "\n")


def verify_configuration():
    """Verifica que la configuración de Notion esté correcta."""
    api_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('NOTION_DATABASE_ID')
    
    print("\n🔍 Verificando configuración...\n")
    
    if not api_key:
        print("❌ NOTION_API_KEY no está configurado en .env")
        return False
    else:
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"✅ NOTION_API_KEY configurado: {masked_key}")
    
    if not database_id:
        print("❌ NOTION_DATABASE_ID no está configurado en .env")
        return False
    else:
        print(f"✅ NOTION_DATABASE_ID configurado: {database_id}")
    
    # Intentar conectar
    try:
        print("\n📡 Intentando conectar con Notion...")
        crm = NotionCRMManager(api_key=api_key, database_id=database_id)
        print("✅ Conexión exitosa con Notion API")
        
        # Intentar leer la base de datos
        print("\n📖 Verificando acceso a la base de datos...")
        contacts = crm.get_all_contacts()
        print(f"✅ Base de datos accesible. Contactos actuales: {len(contacts)}")
        
        if contacts:
            print("\n📋 Últimos 3 contactos en la base de datos:")
            for contact in contacts[:3]:
                print(f"   • {contact['school_name']} ({contact['email']}) - {contact['status']}")
        
        print("\n" + "="*70)
        print("🎉 ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
        print("="*70)
        print("\nYa puedes usar el CRM de Notion. Los colegios contactados se")
        print("registrarán automáticamente cuando envíes presentaciones.\n")
        return True
        
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        return False
    except Exception as e:
        print(f"❌ Error conectando con Notion: {e}")
        print("\n💡 Posibles causas:")
        print("   • El DATABASE_ID no es correcto")
        print("   • La integración no tiene acceso a la base de datos")
        print("   • La estructura de la base de datos no es correcta")
        return False


def test_add_sample_contact():
    """Añade un contacto de prueba a la base de datos."""
    print("\n🧪 ¿Quieres añadir un contacto de prueba? (s/n): ", end='')
    response = input().strip().lower()
    
    if response == 's':
        try:
            crm = NotionCRMManager()
            page_id = crm.add_school_contact(
                school_name="Test School - Colegio de Prueba",
                email="test@testschool.ie",
                school_id="TEST001",
                county="Dublin",
                dublin_zone="North",
                education_level="primary",
                sender_email="test@profesnomadas.com",
                notes="Este es un contacto de prueba. Puedes eliminarlo.",
                status="contacted"
            )
            
            if page_id:
                print(f"✅ Contacto de prueba añadido exitosamente (ID: {page_id})")
                print("   Puedes verlo en tu base de datos de Notion y eliminarlo cuando quieras.")
            else:
                print("❌ No se pudo añadir el contacto de prueba")
        except Exception as e:
            print(f"❌ Error añadiendo contacto de prueba: {e}")


def main():
    """Función principal del script."""
    print("\n🚀 SETUP DE NOTION CRM - PROFES NÓMADAS\n")
    
    # Verificar si las variables están configuradas
    if not os.getenv('NOTION_API_KEY') or not os.getenv('NOTION_DATABASE_ID'):
        print_setup_instructions()
        print("⚠️  Configura las variables de entorno y vuelve a ejecutar este script.\n")
        return
    
    # Verificar configuración
    if verify_configuration():
        test_add_sample_contact()
    else:
        print("\n" + "="*70)
        print("📚 CONSULTA LA DOCUMENTACIÓN ARRIBA PARA CONFIGURAR NOTION")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
