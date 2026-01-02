#!/usr/bin/env python3
"""Script de prueba para verificar conexión a Notion usando NotionCRMManager."""
import os
from datetime import datetime

from src.utils.notion_crm_manager import NotionCRMManager


def main():
    try:
        mgr = NotionCRMManager()
    except Exception as e:
        print("Error inicializando NotionCRMManager:", e)
        return

    print("Probando lectura de contactos existentes...")
    contacts = mgr.get_all_contacts()
    print(f"Encontrados {len(contacts)} contactos (se muestran hasta 5):")
    for c in contacts[:5]:
        print(" -", c.get('school_name'), c.get('email'))

    test_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
    test_name = f"TEST School {test_suffix}"
    test_email = f"test+{test_suffix}@example.com"

    print(f"Añadiendo colegio de prueba: {test_name} ({test_email})")
    page_id = mgr.add_school_contact(
        school_name=test_name,
        email=test_email,
        notes="Prueba automática de conexión",
        sender_email=os.getenv('RESEND_FROM_EMAIL', '')
    )

    if page_id:
        print("✅ Página creada en Notion con ID:", page_id)
        print("Verifica en Notion y elimina el registro de prueba si procede.")
    else:
        print("❌ Falló la creación de la página de prueba.")


if __name__ == '__main__':
    main()
