#!/usr/bin/env python3
"""
Script para crear la plantilla Excel del perfil de usuario
Basado en el ejemplo de Álvaro de Castro Martín
"""

try:
    import pandas as pd
    import openpyxl
    print("✅ Dependencias encontradas: pandas y openpyxl")
except ImportError as e:
    print(f"❌ Error importando dependencias: {e}")
    print("💡 Instalando dependencias...")
    import subprocess
    subprocess.run(["pip", "install", "pandas", "openpyxl"], check=True)
    import pandas as pd
    import openpyxl

import os
from datetime import datetime

def create_profile_template():
    """Crea un archivo Excel de plantilla con el perfil de ejemplo"""
    
    # Información personal
    personal_info = {
        'Campo': ['Nombre Completo', 'Email', 'Teléfono', 'Nacionalidad', 'Fecha de Nacimiento', 'LinkedIn'],
        'Valor': [
            'Álvaro de Castro Martín',
            'alvaro.decastro@ejemplo.com',
            '+34 600 123 456',
            'Española',
            '15/03/1995',
            'https://linkedin.com/in/alvaro-decastro'
        ]
    }
    
    # Experiencia de prácticas docentes
    teaching_practices = {
        'Nombre del Centro': [
            'CEIP Antonio Mingote\'s School',
            'Finnish International School of Tampere',
            'Gredos San Diego Alcalá School',
            'Calasanz\'s Alcalá Piarist School'
        ],
        'Dirección': [
            'C. Arturo Soria, 7, 28806 Alcalá de Henares, Madrid',
            'Satakunnankatu 60, 33230 Tampere, Finlandia',
            'C/ de Octavio Paz, 29, 28806 Alcalá de Henares, Madrid',
            'C. de Santiago, 29, 28801 Alcalá de Henares, Madrid'
        ],
        'Edades/Cursos Impartidos': [
            '(6-7 años) y (7-8 años)',
            '(10-11 años) y (11-12 años)',
            '(8-9 años), (9-10 años) y (10-11 años)',
            '(5-6 años) y (6-7 años)'
        ],
        'Asignaturas Impartidas': [
            'English, Natural Science, Social Science and Maths',
            'English, Social Studies, Maths and Religion',
            'English, Social Studies, Natural Sciences and Arts',
            'Matemáticas, Lengua, Ciencias Naturales'
        ],
        'Fechas': [
            '22/11/2021 - 22/12/2021',
            '16/01/2023 - 23/02/2023',
            '22/01/2024 - 05/04/2024',
            '11/11/2024 - 20/12/2024'
        ],
        'Calificación': [
            '9.60/10',
            '9.60/10',
            '9.80/10',
            '9.70/10'
        ],
        'Observaciones': [
            'Excelente adaptación al entorno bilingüe',
            'Experiencia internacional en Finlandia',
            'Trabajo multidisciplinar con diferentes edades',
            'Práctica actual en curso'
        ]
    }
    
    # Formación académica
    education = {
        'Título': [
            'Grado en Educación Primaria',
            'Máster en Educación Bilingüe',
            'Certificado C1 Cambridge English',
            'Curso de Metodologías Activas'
        ],
        'Institución': [
            'Universidad de Alcalá',
            'Universidad Complutense de Madrid',
            'Cambridge English Assessment',
            'Centro de Formación Continua'
        ],
        'Año de Finalización': [
            '2021',
            '2022',
            '2020',
            '2023'
        ],
        'Nota/Calificación': [
            '8.5/10',
            '9.2/10',
            'C1 Advanced',
            'Sobresaliente'
        ]
    }
    
    # Habilidades y competencias
    skills = {
        'Categoría': [
            'Idiomas',
            'Idiomas',
            'Tecnología Educativa',
            'Tecnología Educativa',
            'Metodologías',
            'Metodologías',
            'Soft Skills',
            'Soft Skills'
        ],
        'Habilidad': [
            'Inglés',
            'Finés (básico)',
            'Google Classroom',
            'Microsoft Office Suite',
            'Aprendizaje Basado en Proyectos',
            'Gamificación',
            'Trabajo en equipo',
            'Adaptabilidad cultural'
        ],
        'Nivel': [
            'C1 Avanzado',
            'A2 Básico',
            'Avanzado',
            'Experto',
            'Avanzado',
            'Intermedio',
            'Excelente',
            'Excelente'
        ]
    }
    
    # Motivación y objetivos
    motivation = {
        'Aspecto': [
            'Motivación Principal',
            'Objetivo Profesional',
            'Países de Interés',
            'Tipo de Centro Preferido',
            'Especialización Deseada',
            'Disponibilidad'
        ],
        'Descripción': [
            'Expandir mi experiencia docente internacional y aportar metodologías innovadoras en entornos multiculturales',
            'Desarrollar competencias en educación bilingüe y metodologías europeas avanzadas',
            'Irlanda, Reino Unido, Países Nórdicos',
            'Centros bilingües e internacionales con enfoque innovador',
            'Educación bilingüe, STEAM, metodologías activas',
            'Inmediata - Flexible para reubicación'
        ]
    }
    
    # Crear el archivo Excel con múltiples hojas
    filename = 'Plantilla_Perfil_Profesional.xlsx'
    filepath = os.path.join('/Users/raulfortea/Projects/ScrapingProfesNomadas', filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Hoja 1: Información Personal
        df_personal = pd.DataFrame(personal_info)
        df_personal.to_excel(writer, sheet_name='Información Personal', index=False)
        
        # Hoja 2: Prácticas Docentes
        df_teaching = pd.DataFrame(teaching_practices)
        df_teaching.to_excel(writer, sheet_name='Prácticas Docentes', index=False)
        
        # Hoja 3: Formación Académica
        df_education = pd.DataFrame(education)
        df_education.to_excel(writer, sheet_name='Formación Académica', index=False)
        
        # Hoja 4: Habilidades
        df_skills = pd.DataFrame(skills)
        df_skills.to_excel(writer, sheet_name='Habilidades', index=False)
        
        # Hoja 5: Motivación
        df_motivation = pd.DataFrame(motivation)
        df_motivation.to_excel(writer, sheet_name='Motivación y Objetivos', index=False)
    
    print(f"✅ Plantilla Excel creada: {filename}")
    print(f"📁 Ubicación: {filepath}")
    
    # Crear también una versión simplificada para usuarios
    create_simple_template()
    
def create_simple_template():
    """Crea una versión simplificada de la plantilla para que los usuarios la completen"""
    
    # Plantilla simplificada para que el usuario complete
    personal_info = {
        'Campo': ['Nombre Completo', 'Email', 'Teléfono', 'Nacionalidad', 'Fecha de Nacimiento', 'LinkedIn'],
        'Valor': [
            '[Tu nombre completo]',
            '[tu.email@ejemplo.com]',
            '[+34 XXX XXX XXX]',
            '[Tu nacionalidad]',
            '[DD/MM/AAAA]',
            '[Tu perfil de LinkedIn]'
        ]
    }
    
    teaching_practices = {
        'Nombre del Centro': [
            '[Nombre del primer centro]',
            '[Nombre del segundo centro]',
            '[Añade más filas según necesites]'
        ],
        'Dirección': [
            '[Dirección completa del centro]',
            '[Dirección completa del centro]',
            '[Dirección completa del centro]'
        ],
        'Edades/Cursos Impartidos': [
            '[Ej: (6-7 años) y (7-8 años)]',
            '[Ej: (10-11 años)]',
            '[Especifica las edades]'
        ],
        'Asignaturas Impartidas': [
            '[Ej: English, Maths, Science]',
            '[Lista las asignaturas]',
            '[Materias que has impartido]'
        ],
        'Fechas': [
            '[DD/MM/AAAA - DD/MM/AAAA]',
            '[DD/MM/AAAA - DD/MM/AAAA]',
            '[DD/MM/AAAA - DD/MM/AAAA]'
        ],
        'Calificación': [
            '[Ej: 9.60/10]',
            '[Tu calificación]',
            '[Nota obtenida]'
        ],
        'Observaciones': [
            '[Aspectos destacados de esta práctica]',
            '[Logros o aprendizajes especiales]',
            '[Comentarios adicionales]'
        ]
    }
    
    education = {
        'Título': [
            '[Ej: Grado en Educación Primaria]',
            '[Ej: Máster en...]',
            '[Otros títulos o certificaciones]'
        ],
        'Institución': [
            '[Universidad o centro]',
            '[Universidad o centro]',
            '[Universidad o centro]'
        ],
        'Año de Finalización': [
            '[AAAA]',
            '[AAAA]',
            '[AAAA]'
        ],
        'Nota/Calificación': [
            '[Ej: 8.5/10]',
            '[Tu calificación]',
            '[Nota obtenida]'
        ]
    }
    
    skills = {
        'Categoría': [
            'Idiomas',
            'Idiomas',
            'Tecnología Educativa',
            'Metodologías',
            'Soft Skills'
        ],
        'Habilidad': [
            '[Ej: Inglés]',
            '[Ej: Francés]',
            '[Ej: Google Classroom]',
            '[Ej: ABP - Aprendizaje Basado en Proyectos]',
            '[Ej: Trabajo en equipo]'
        ],
        'Nivel': [
            '[Ej: C1 Avanzado]',
            '[Ej: B2 Intermedio]',
            '[Básico/Intermedio/Avanzado/Experto]',
            '[Básico/Intermedio/Avanzado]',
            '[Básico/Bueno/Excelente]'
        ]
    }
    
    motivation = {
        'Aspecto': [
            'Motivación Principal',
            'Objetivo Profesional',
            'Países de Interés',
            'Tipo de Centro Preferido',
            'Especialización Deseada',
            'Disponibilidad'
        ],
        'Descripción': [
            '[Describe tu principal motivación para enseñar en el extranjero]',
            '[Qué esperas lograr profesionalmente]',
            '[Ej: Irlanda, Reino Unido, etc.]',
            '[Ej: Centros bilingües, internacionales, públicos, privados]',
            '[Ej: Educación bilingüe, STEAM, etc.]',
            '[Ej: Inmediata, a partir de septiembre 2025, etc.]'
        ]
    }
    
    # Crear archivo de plantilla vacía
    filename = 'MI_PERFIL_PROFESIONAL_PLANTILLA.xlsx'
    filepath = os.path.join('/Users/raulfortea/Projects/ScrapingProfesNomadas', filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df_personal = pd.DataFrame(personal_info)
        df_personal.to_excel(writer, sheet_name='Información Personal', index=False)
        
        df_teaching = pd.DataFrame(teaching_practices)
        df_teaching.to_excel(writer, sheet_name='Prácticas Docentes', index=False)
        
        df_education = pd.DataFrame(education)
        df_education.to_excel(writer, sheet_name='Formación Académica', index=False)
        
        df_skills = pd.DataFrame(skills)
        df_skills.to_excel(writer, sheet_name='Habilidades', index=False)
        
        df_motivation = pd.DataFrame(motivation)
        df_motivation.to_excel(writer, sheet_name='Motivación y Objetivos', index=False)
    
    print(f"✅ Plantilla vacía creada: {filename}")
    print(f"📁 Los usuarios pueden completar esta plantilla con sus datos")

def create_instructions_file():
    """Crea un archivo con instrucciones para usar la plantilla"""
    
    instructions = """
# 📊 GUÍA: Cómo usar la Plantilla de Perfil Profesional

## 🎯 Propósito
Este archivo Excel te ayudará a organizar toda tu información profesional para que el bot pueda generar emails personalizados y únicos usando IA.

## 📋 Estructura del Archivo

### 1. **Información Personal**
- Completa todos los campos básicos
- El email debe ser el mismo que usarás para enviar las solicitudes
- LinkedIn es opcional pero recomendado

### 2. **Prácticas Docentes** ⭐ MUY IMPORTANTE
- **Esta es la sección más crucial para el scraping educativo**
- Añade TODAS tus prácticas docentes (practicum, prácticas profesionales, etc.)
- Incluye información detallada de cada centro donde has hecho prácticas
- La IA usará esta información para personalizar cada email según el centro de destino

#### Campos importantes:
- **Nombre del Centro**: Nombre completo y exacto
- **Dirección**: Dirección completa (ayuda a identificar el tipo de zona/centro)
- **Edades/Cursos**: Especifica exactamente las edades con las que trabajaste
- **Asignaturas**: Lista todas las materias que impartiste
- **Fechas**: Periodo exacto de las prácticas
- **Calificación**: Tu nota o evaluación
- **Observaciones**: Aspectos destacados, logros especiales, aprendizajes

### 3. **Formación Académica**
- Incluye grados, másteres, certificaciones
- Las certificaciones de idiomas son muy importantes
- Añade cursos especializados relevantes

### 4. **Habilidades**
- **Idiomas**: Especifica el nivel exacto (A1, A2, B1, B2, C1, C2)
- **Tecnología Educativa**: Herramientas que manejas
- **Metodologías**: Enfoques pedagógicos que dominas
- **Soft Skills**: Habilidades interpersonales

### 5. **Motivación y Objetivos**
- La IA usará esta información para personalizar el tono y enfoque de cada email
- Sé específico sobre tus objetivos
- Menciona qué puedes aportar a los centros

## 🤖 Cómo la IA usa esta información

1. **Personalización por Centro**: Compara tu experiencia con el tipo de centro de destino
2. **Adaptación de Metodologías**: Destaca las metodologías relevantes para cada institución
3. **Experiencia Relevante**: Resalta la experiencia más similar al puesto solicitado
4. **Tono Personalizado**: Adapta el tono según el tipo de centro (público, privado, internacional)
5. **Objetivos Alineados**: Conecta tus objetivos con la misión del centro

## ✅ Consejos para Completar la Plantilla

### DO (Hacer):
- ✅ Sé específico y detallado
- ✅ Incluye TODAS tus prácticas, incluso las cortas
- ✅ Menciona logros cuantificables cuando sea posible
- ✅ Actualiza regularmente la información
- ✅ Revisa la ortografía y gramática

### DON'T (No hacer):
- ❌ No dejes campos vacíos (usa "N/A" si no aplica)
- ❌ No uses abreviaciones poco claras
- ❌ No incluyas información falsa
- ❌ No olvides actualizar fechas y logros recientes

## 📤 Uso en el Bot

1. Completa la plantilla con tus datos
2. Guarda el archivo como `.xlsx`
3. Envía el archivo al bot cuando te lo solicite
4. El bot analizará tu perfil y generará emails únicos para cada centro

## 🔄 Mantenimiento

- Actualiza el archivo cada vez que completes nuevas prácticas
- Añade nuevas certificaciones o formaciones
- Revisa y mejora la información periódicamente

---

💡 **Tip**: Cuanta más información de calidad proporciones, mejores y más personalizados serán los emails generados por la IA.
"""
    
    filepath = '/Users/raulfortea/Projects/ScrapingProfesNomadas/INSTRUCCIONES_PLANTILLA_EXCEL.md'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    print(f"✅ Instrucciones creadas: INSTRUCCIONES_PLANTILLA_EXCEL.md")

if __name__ == "__main__":
    print("📊 Creando plantillas de perfil profesional...")
    print("=" * 50)
    
    create_profile_template()
    create_simple_template()
    create_instructions_file()
    
    print("\n🎉 ¡Plantillas creadas exitosamente!")
    print("\nArchivos generados:")
    print("1. Plantilla_Perfil_Profesional.xlsx - Ejemplo completo con datos de Álvaro")
    print("2. MI_PERFIL_PROFESIONAL_PLANTILLA.xlsx - Plantilla vacía para completar")
    print("3. INSTRUCCIONES_PLANTILLA_EXCEL.md - Guía completa de uso")
