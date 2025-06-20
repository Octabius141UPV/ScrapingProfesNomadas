#!/usr/bin/env python3
"""
Script para generar template de Excel para ScrapingProfesNomadas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_email_generator_v2 import AIEmailGeneratorV2

def main():
    """Genera template de Excel para que los usuarios llenen sus datos"""
    print("🎓 ScrapingProfesNomadas - Generador de Template Excel")
    print("=" * 55)
    
    generator = AIEmailGeneratorV2()
    
    # Verificar características disponibles
    features = generator.get_available_features()
    print(f"📊 Características disponibles: {features}")
    
    if not features['excel_support']:
        print("❌ No hay soporte para Excel disponible")
        print("💡 Instala pandas u openpyxl: pip install pandas openpyxl")
        return False
    
    # Solicitar nombre del archivo
    while True:
        filename = input("\n📊 Nombre del archivo Excel (o Enter para usar 'user_profile_template.xlsx'): ").strip()
        
        if not filename:
            filename = "user_profile_template.xlsx"
            break
        elif not filename.endswith(('.xlsx', '.xls')):
            filename += '.xlsx'
            break
    
    print(f"\n🔄 Generando template: {filename}")
    
    # Crear template
    result = generator.create_excel_template(filename)
    
    if result:
        print(f"✅ Template creado exitosamente: {filename}")
        print("\n📋 Instrucciones:")
        print("1. Abre el archivo Excel generado")
        print("2. Llena tus datos en la fila existente")
        print("3. Puedes añadir más filas para múltiples perfiles")
        print("4. Guarda el archivo")
        print("5. Envía el archivo Excel al bot de Telegram")
        print("\n💡 Campos del template:")
        print("• name: Tu nombre completo")
        print("• email: Tu email de contacto")
        print("• phone: Tu teléfono")
        print("• experience: Años y tipo de experiencia")
        print("• education: Nivel educativo y universidad")
        print("• skills: Habilidades separadas por comas")
        print("• specialization: Especialización principal")
        print("• languages: Idiomas separados por comas")
        print("• certifications: Certificaciones obtenidas")
        print("• motivation: Motivación personal")
        
        # Crear también versión JSON como backup
        json_filename = filename.replace('.xlsx', '.json').replace('.xls', '.json')
        generator.save_profile_as_json({
            'name': 'Juan Pérez',
            'email': 'juan.perez@email.com',
            'phone': '123-456-789',
            'experience': '5 años como profesor de matemáticas',
            'education': 'Licenciatura en Matemáticas, Universidad XYZ',
            'skills': 'Python, metodologías activas, manejo de aulas virtuales',
            'specialization': 'Educación Secundaria',
            'languages': 'Español (nativo), Inglés (avanzado)',
            'certifications': 'Certificación en TIC educativas',
            'motivation': 'Pasión por la enseñanza y el desarrollo estudiantil'
        }, json_filename)
        
        print(f"📄 También se creó backup JSON: {json_filename}")
        return True
    else:
        print("❌ Error creando template")
        return False
        print("• achievements: Logros separados por comas")
        print("• personal_statement: Declaración personal breve")
        print("• preferred_locations: Ubicaciones preferidas separadas por comas")
        print("• availability: Disponibilidad (ej: Immediate, 1 month)")
        
        print("\n🤖 Con estos datos, la IA generará emails únicos y personalizados para cada institución educativa.")
        
    else:
        print("❌ Error generando template")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Generación cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
