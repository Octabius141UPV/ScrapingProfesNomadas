#!/usr/bin/env python3
"""
Script de utilidad para gestionar el CRM de Notion desde línea de comandos.
Permite consultar, actualizar y gestionar contactos de colegios.
"""
import os
import sys
import argparse
from typing import Optional
from dotenv import load_dotenv

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv(override=True)

from src.utils.notion_crm_manager import NotionCRMManager


def list_contacts(crm: NotionCRMManager, status: Optional[str] = None):
    """Lista todos los contactos, opcionalmente filtrados por estado."""
    print("\n📋 Obteniendo contactos del CRM...")
    contacts = crm.get_all_contacts(status_filter=status)
    
    if not contacts:
        print("❌ No se encontraron contactos" + (f" con estado '{status}'" if status else ""))
        return
    
    print(f"\n✅ Encontrados {len(contacts)} contactos" + (f" con estado '{status}'" if status else "") + ":\n")
    print("-" * 100)
    print(f"{'School Name':<35} {'Email':<30} {'Status':<15} {'Date':<12}")
    print("-" * 100)
    
    for contact in contacts:
        school_name = contact['school_name'][:34] if contact['school_name'] else 'N/A'
        email = contact['email'][:29] if contact['email'] else 'N/A'
        status_val = contact['status'][:14] if contact['status'] else 'N/A'
        date = contact['contact_date'][:10] if contact['contact_date'] else 'N/A'
        print(f"{school_name:<35} {email:<30} {status_val:<15} {date:<12}")
    
    print("-" * 100)
    print(f"\nTotal: {len(contacts)} contactos\n")


def add_contact(
    crm: NotionCRMManager,
    school_name: str,
    email: str,
    school_id: str = "",
    county: str = "",
    dublin_zone: str = "",
    education_level: str = "primary",
    sender_email: str = "",
    notes: str = "",
    status: str = "contacted"
):
    """Añade un nuevo contacto al CRM."""
    print(f"\n📝 Añadiendo contacto: {school_name} ({email})...")
    
    page_id = crm.add_school_contact(
        school_name=school_name,
        email=email,
        school_id=school_id,
        county=county,
        dublin_zone=dublin_zone,
        education_level=education_level,
        sender_email=sender_email,
        notes=notes,
        status=status
    )
    
    if page_id:
        print(f"✅ Contacto añadido exitosamente (ID: {page_id})")
    else:
        print("❌ No se pudo añadir el contacto")


def update_status(crm: NotionCRMManager, email: str, new_status: str, notes: str = ""):
    """Actualiza el estado de un contacto por email."""
    print(f"\n🔄 Buscando contacto con email: {email}...")
    
    # Buscar el contacto
    existing = crm._find_school_by_email(email)
    
    if not existing:
        print(f"❌ No se encontró un contacto con email: {email}")
        return
    
    page_id = existing['id']
    school_name = crm._extract_title(existing['properties'].get('School Name', {}))
    
    print(f"📝 Actualizando {school_name} a estado '{new_status}'...")
    
    result = crm.update_school_contact(
        page_id=page_id,
        status=new_status,
        notes=notes if notes else f"Estado actualizado a {new_status}"
    )
    
    if result:
        print(f"✅ Contacto actualizado exitosamente")
    else:
        print("❌ No se pudo actualizar el contacto")


def stats(crm: NotionCRMManager):
    """Muestra estadísticas del CRM."""
    print("\n📊 Obteniendo estadísticas del CRM...\n")
    
    all_contacts = crm.get_all_contacts()
    
    if not all_contacts:
        print("❌ No hay contactos en el CRM")
        return
    
    # Contar por estado
    status_counts = {}
    county_counts = {}
    level_counts = {}
    
    for contact in all_contacts:
        status = contact['status'] or 'sin_estado'
        county = contact['county'] or 'sin_condado'
        level = contact['education_level'] or 'sin_nivel'
        
        status_counts[status] = status_counts.get(status, 0) + 1
        county_counts[county] = county_counts.get(county, 0) + 1
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print(f"Total de contactos: {len(all_contacts)}\n")
    
    print("Por estado:")
    for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {status}: {count}")
    
    print("\nPor condado:")
    for county, count in sorted(county_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {county}: {count}")
    
    print("\nPor nivel educativo:")
    for level, count in sorted(level_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {level}: {count}")
    
    print()


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description="Gestión del CRM de Notion para Profes Nómadas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Listar todos los contactos
  python scripts/manage_notion_crm.py list

  # Listar contactos con estado específico
  python scripts/manage_notion_crm.py list --status interested

  # Añadir un nuevo contacto
  python scripts/manage_notion_crm.py add \\
    --school "St. Mary's Primary" \\
    --email "office@stmarys.ie" \\
    --county Dublin \\
    --level primary

  # Actualizar estado de un contacto
  python scripts/manage_notion_crm.py update \\
    --email "office@stmarys.ie" \\
    --status followed_up \\
    --notes "Llamada realizada el 10/12/2025"

  # Ver estadísticas
  python scripts/manage_notion_crm.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comando a ejecutar')
    
    # Comando list
    list_parser = subparsers.add_parser('list', help='Listar contactos')
    list_parser.add_argument('--status', help='Filtrar por estado')
    
    # Comando add
    add_parser = subparsers.add_parser('add', help='Añadir un nuevo contacto')
    add_parser.add_argument('--school', required=True, help='Nombre del colegio')
    add_parser.add_argument('--email', required=True, help='Email del colegio')
    add_parser.add_argument('--school-id', default='', help='ID del colegio (roll number)')
    add_parser.add_argument('--county', default='', help='Condado')
    add_parser.add_argument('--dublin-zone', default='', help='Zona de Dublin')
    add_parser.add_argument('--level', default='primary', choices=['primary', 'secondary'], 
                          help='Nivel educativo')
    add_parser.add_argument('--sender', default='', help='Email del remitente')
    add_parser.add_argument('--notes', default='', help='Notas adicionales')
    add_parser.add_argument('--status', default='contacted', 
                          choices=['contacted', 'followed_up', 'interested', 'not_interested', 'hired'],
                          help='Estado inicial')
    
    # Comando update
    update_parser = subparsers.add_parser('update', help='Actualizar un contacto')
    update_parser.add_argument('--email', required=True, help='Email del contacto a actualizar')
    update_parser.add_argument('--status', required=True,
                             choices=['contacted', 'followed_up', 'interested', 'not_interested', 'hired'],
                             help='Nuevo estado')
    update_parser.add_argument('--notes', default='', help='Notas adicionales')
    
    # Comando stats
    stats_parser = subparsers.add_parser('stats', help='Ver estadísticas del CRM')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Inicializar CRM
    try:
        crm = NotionCRMManager()
    except (ValueError, ImportError) as e:
        print(f"❌ Error inicializando Notion CRM: {e}")
        print("\n💡 Asegúrate de que:")
        print("   1. notion-client está instalado: pip install notion-client")
        print("   2. NOTION_API_KEY está configurado en .env")
        print("   3. NOTION_DATABASE_ID está configurado en .env")
        print("\nPara más información, ejecuta: python scripts/setup_notion_crm.py")
        return
    
    # Ejecutar comando
    if args.command == 'list':
        list_contacts(crm, status=args.status)
    
    elif args.command == 'add':
        add_contact(
            crm,
            school_name=args.school,
            email=args.email,
            school_id=args.school_id,
            county=args.county,
            dublin_zone=args.dublin_zone,
            education_level=args.level,
            sender_email=args.sender,
            notes=args.notes,
            status=args.status
        )
    
    elif args.command == 'update':
        update_status(crm, email=args.email, new_status=args.status, notes=args.notes)
    
    elif args.command == 'stats':
        stats(crm)


if __name__ == "__main__":
    main()
