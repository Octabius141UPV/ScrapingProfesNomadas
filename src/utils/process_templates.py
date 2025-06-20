#!/usr/bin/env python3
"""
Script para convertir las plantillas CSV a un archivo Excel consolidado
"""

import csv
import json
import os

def csv_to_dict(filepath):
    """Convierte un CSV a diccionario"""
    data = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    return data

def create_excel_data_json():
    """Crea un archivo JSON con los datos para Excel"""
    
    base_path = '/Users/raulfortea/Projects/ScrapingProfesNomadas'
    
    # Leer todos los CSV de ejemplo
    excel_data = {
        'Información Personal': csv_to_dict(f'{base_path}/ejemplo_informacion_personal.csv'),
        'Prácticas Docentes': csv_to_dict(f'{base_path}/ejemplo_practicas_docentes.csv'),
        'Formación Académica': csv_to_dict(f'{base_path}/ejemplo_formacion_academica.csv'),
        'Habilidades': csv_to_dict(f'{base_path}/ejemplo_habilidades.csv'),
        'Motivación': csv_to_dict(f'{base_path}/ejemplo_motivacion.csv')
    }
    
    # Guardar como JSON para uso posterior
    with open(f'{base_path}/perfil_ejemplo_data.json', 'w', encoding='utf-8') as f:
        json.dump(excel_data, f, indent=2, ensure_ascii=False)
    
    print("✅ Datos del perfil guardados en: perfil_ejemplo_data.json")
    
    # También crear plantillas vacías
    plantilla_data = {
        'Información Personal': csv_to_dict(f'{base_path}/plantilla_informacion_personal.csv'),
        'Prácticas Docentes': csv_to_dict(f'{base_path}/plantilla_practicas_docentes.csv'),
        'Formación Académica': csv_to_dict(f'{base_path}/plantilla_formacion_academica.csv'),
        'Habilidades': csv_to_dict(f'{base_path}/plantilla_habilidades.csv'),
        'Motivación': csv_to_dict(f'{base_path}/plantilla_motivacion.csv')
    }
    
    with open(f'{base_path}/plantilla_vacia_data.json', 'w', encoding='utf-8') as f:
        json.dump(plantilla_data, f, indent=2, ensure_ascii=False)
    
    print("✅ Plantilla vacía guardada en: plantilla_vacia_data.json")

def create_instructions_html():
    """Crea una versión HTML de las instrucciones para mejor visualización"""
    
    html_content = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guía de Plantillas - ScrapingProfesNomadas</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; }
        h2 { color: #34495e; margin-top: 30px; }
        h3 { color: #7f8c8d; }
        .important { background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }
        .tip { background-color: #d1ecf1; padding: 15px; border-left: 4px solid #17a2b8; margin: 20px 0; }
        .warning { background-color: #f8d7da; padding: 15px; border-left: 4px solid #dc3545; margin: 20px 0; }
        .success { background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0; }
        ul, ol { padding-left: 30px; }
        code { background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px; }
        .file-list { background-color: #f8f9fa; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>📊 Guía de Plantillas de Perfil Profesional</h1>
    
    <div class="important">
        <strong>🎯 Propósito:</strong> Estas plantillas organizan tu información profesional para que la IA genere emails personalizados únicos para cada institución educativa.
    </div>
    
    <h2>📁 Archivos Disponibles</h2>
    
    <div class="file-list">
        <h3>📋 Ejemplos Completos:</h3>
        <ul>
            <li><code>ejemplo_informacion_personal.csv</code> - Datos personales de ejemplo</li>
            <li><code>ejemplo_practicas_docentes.csv</code> - Experiencia en prácticas docentes</li>
            <li><code>ejemplo_formacion_academica.csv</code> - Estudios y certificaciones</li>
            <li><code>ejemplo_habilidades.csv</code> - Competencias técnicas y soft skills</li>
            <li><code>ejemplo_motivacion.csv</code> - Objetivos y motivaciones</li>
        </ul>
        
        <h3>📝 Plantillas para Completar:</h3>
        <ul>
            <li><code>plantilla_informacion_personal.csv</code> - Completa con tus datos</li>
            <li><code>plantilla_practicas_docentes.csv</code> - Tu experiencia docente</li>
            <li><code>plantilla_formacion_academica.csv</code> - Tus estudios</li>
            <li><code>plantilla_habilidades.csv</code> - Tus competencias</li>
            <li><code>plantilla_motivacion.csv</code> - Tus objetivos</li>
        </ul>
    </div>
    
    <h2>🎓 Prácticas Docentes - Sección MÁS IMPORTANTE</h2>
    
    <div class="important">
        <strong>⭐ ¡CRÍTICO!</strong> Esta es la sección más importante para el sistema de scraping educativo.
        <br><br>
        <strong>¿Por qué?</strong>
        <ul>
            <li>La IA analiza tu experiencia para personalizar cada email</li>
            <li>Compara tus prácticas con el centro de destino</li>
            <li>Adapta el mensaje según similitudes encontradas</li>
        </ul>
    </div>
    
    <h3>Campos Críticos:</h3>
    <ul>
        <li><strong>Nombre del Centro:</strong> Exacto y completo</li>
        <li><strong>Dirección:</strong> Completa (identifica tipo de zona/contexto)</li>
        <li><strong>Edades/Cursos:</strong> Específico (ej: "(6-7 años) y (7-8 años)")</li>
        <li><strong>Asignaturas:</strong> Lista completa de materias impartidas</li>
        <li><strong>Fechas:</strong> Periodo exacto (DD/MM/AAAA - DD/MM/AAAA)</li>
        <li><strong>Calificación:</strong> Tu evaluación final</li>
        <li><strong>Observaciones:</strong> Logros, aprendizajes, aspectos destacados</li>
    </ul>
    
    <div class="tip">
        <strong>💡 Consejos:</strong>
        <ul>
            <li>Incluye TODAS tus prácticas, incluso las cortas</li>
            <li>Sé específico en las observaciones</li>
            <li>Menciona metodologías especiales que usaste</li>
            <li>Destaca logros cuantificables</li>
        </ul>
    </div>
    
    <h2>🤖 Cómo la IA Usa Tu Información</h2>
    
    <div class="success">
        <h3>Personalización Automática:</h3>
        <ol>
            <li><strong>Análisis de Compatibilidad:</strong> Compara tu experiencia con cada centro</li>
            <li><strong>Adaptación Metodológica:</strong> Destaca metodologías relevantes</li>
            <li><strong>Experiencia Relevante:</strong> Resalta experiencia similar al puesto</li>
            <li><strong>Tono Personalizado:</strong> Adapta según tipo de centro</li>
            <li><strong>Conexión de Objetivos:</strong> Alinea tus metas con la misión del centro</li>
        </ol>
    </div>
    
    <h3>Ejemplos de Personalización:</h3>
    <ul>
        <li><strong>Centro bilingüe:</strong> Destaca experiencia con inglés y certificaciones</li>
        <li><strong>Centro internacional:</strong> Enfatiza experiencia en Finlandia</li>
        <li><strong>Primaria temprana:</strong> Resalta trabajo con edades 5-7 años</li>
        <li><strong>Centro innovador:</strong> Menciona metodologías activas y tecnología</li>
    </ul>
    
    <h2>🚨 Errores Comunes a Evitar</h2>
    
    <div class="warning">
        <h3>❌ NO hagas esto:</h3>
        <ul>
            <li>Dejar campos vacíos (usa "N/A" si no aplica)</li>
            <li>Usar abreviaciones poco claras</li>
            <li>Información falsa o exagerada</li>
            <li>Fechas en formato incorrecto</li>
            <li>Niveles de idioma inexactos</li>
        </ul>
    </div>
    
    <div class="success">
        <h3>✅ SÍ haz esto:</h3>
        <ul>
            <li>Sé específico y detallado</li>
            <li>Usa información verificable</li>
            <li>Mantén fechas actualizadas</li>
            <li>Revisa ortografía y gramática</li>
            <li>Incluye logros cuantificables</li>
        </ul>
    </div>
    
    <h2>🔄 Proceso en el Bot</h2>
    
    <ol>
        <li><strong>Inicio:</strong> Comando <code>/start</code> en el bot</li>
        <li><strong>Datos básicos:</strong> Nombre, email, contraseña de aplicación</li>
        <li><strong>Documentos:</strong> Opcionalmente envía CV, certificados</li>
        <li><strong>Perfil Excel:</strong> Envía tu archivo completado</li>
        <li><strong>Procesamiento:</strong> El bot analiza tu perfil con IA</li>
        <li><strong>Búsqueda:</strong> Scraping automático de ofertas educativas</li>
        <li><strong>Emails personalizados:</strong> Generación automática para cada centro</li>
        <li><strong>Envío:</strong> Solicitudes enviadas automáticamente</li>
    </ol>
    
    <div class="tip">
        <strong>💡 Recuerda:</strong> Cuanta más información de calidad proporciones, mejores y más personalizados serán los emails generados por la IA.
    </div>
    
</body>
</html>
"""
    
    filepath = '/Users/raulfortea/Projects/ScrapingProfesNomadas/guia_plantillas.html'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ Guía HTML creada: guia_plantillas.html")

if __name__ == "__main__":
    print("📊 Procesando plantillas CSV...")
    print("=" * 50)
    
    create_excel_data_json()
    create_instructions_html()
    
    print("\n🎉 ¡Procesamiento completado!")
    print("\nArchivos creados:")
    print("• perfil_ejemplo_data.json - Datos de ejemplo en formato JSON")
    print("• plantilla_vacia_data.json - Plantilla vacía en formato JSON") 
    print("• guia_plantillas.html - Guía visual en HTML")
    print("\n💡 Los usuarios pueden:")
    print("  1. Abrir los CSV en Excel/Google Sheets")
    print("  2. Completar con sus datos")
    print("  3. Guardar como archivo Excel (.xlsx)")
    print("  4. Enviar al bot de Telegram")
