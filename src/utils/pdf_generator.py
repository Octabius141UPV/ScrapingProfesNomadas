#!/usr/bin/env python3
"""
No Generador de PDFs para formularios de aplicación y conversión de Excel
"""

import os
from fpdf import FPDF
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime
import logging
import unicodedata
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

logger = logging.getLogger(__name__)

class PDFGenerator:
    def __init__(self):
        """Inicializa el generador de PDFs"""
        # Configuración para FPDF (Excel a PDF)
        self.pdf = FPDF()
        self.pdf.add_page()
        self.pdf.set_auto_page_break(auto=True, margin=15)
        
        # Configuración para ReportLab (Formularios de aplicación)
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=12
        )
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitiza el texto para evitar problemas de codificación
        
        Args:
            text: Texto a sanitizar
            
        Returns:
            Texto sanitizado
        """
        if not isinstance(text, str):
            return str(text)
            
        # Reemplazar caracteres especiales
        replacements = {
            '\u2019': "'",  # Apóstrofe tipográfico
            '\u2018': "'",  # Comilla simple izquierda
            '\u201c': '"',  # Comilla doble izquierda
            '\u201d': '"',  # Comilla doble derecha
            '\u2013': '-',  # Guión medio
            '\u2014': '--', # Guión largo
            '\u2026': '...' # Puntos suspensivos
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        # Normalizar caracteres Unicode
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        
        return text
    
    def generate_referentes_pdf(self, excel_path: str) -> str:
        """
        Genera un PDF con los datos de referentes en inglés
        
        Args:
            excel_path: Ruta al archivo Excel de referentes
            
        Returns:
            Ruta al PDF generado
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(excel_path):
                raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")
            
            # Leer el Excel
            logger.info(f"Leyendo Excel: {excel_path}")
            df = pd.read_excel(excel_path)
            
            if df.empty:
                raise ValueError("El archivo Excel está vacío")
            
            # Crear nuevo PDF
            self.pdf = FPDF()
            self.pdf.add_page()
            self.pdf.set_auto_page_break(auto=True, margin=15)
            
            # Configurar el PDF
            self.pdf.set_font("Arial", "B", 16)
            self.pdf.cell(0, 10, "Reference Contacts", ln=True, align="C")
            self.pdf.ln(10)
            
            # Añadir fecha
            self.pdf.set_font("Arial", "I", 10)
            self.pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
            self.pdf.ln(10)
            
            # Añadir contenido
            self.pdf.set_font("Arial", "", 12)
            
            # Procesar cada fila
            for index, row in df.iterrows():
                logger.info(f"Procesando fila {index + 1}")
                
                # Añadir cada campo con su etiqueta en inglés
                for column in df.columns:
                    value = str(row[column])
                    if pd.notna(value) and value.strip():
                        # Sanitizar el texto
                        value = self._sanitize_text(value)
                        
                        # Traducir el nombre de la columna al inglés
                        column_en = self._translate_column_name(column)
                        self.pdf.set_font("Arial", "B", 12)
                        self.pdf.cell(0, 10, f"{column_en}:", ln=True)
                        self.pdf.set_font("Arial", "", 12)
                        self.pdf.multi_cell(0, 10, value)
                        self.pdf.ln(5)
                
                self.pdf.ln(10)
            
            # Guardar el PDF
            output_path = excel_path.replace('.xlsx', '_references.pdf')
            logger.info(f"Guardando PDF en: {output_path}")
            self.pdf.output(output_path)
            
            # Verificar que el PDF se creó correctamente
            if not os.path.exists(output_path):
                raise Exception("No se pudo crear el archivo PDF")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error en generate_referentes_pdf: {str(e)}")
            raise
    
    def generate_practicas_pdf(self, excel_path: str) -> str:
        """
        Genera un PDF con los datos de prácticas en inglés
        
        Args:
            excel_path: Ruta al archivo Excel de prácticas
            
        Returns:
            Ruta al PDF generado
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(excel_path):
                raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")
            
            # Leer el Excel
            logger.info(f"Leyendo Excel: {excel_path}")
            df = pd.read_excel(excel_path)
            
            if df.empty:
                raise ValueError("El archivo Excel está vacío")
            
            # Crear nuevo PDF
            self.pdf = FPDF()
            self.pdf.add_page()
            self.pdf.set_auto_page_break(auto=True, margin=15)
            
            # Configurar el PDF
            self.pdf.set_font("Arial", "B", 16)
            self.pdf.cell(0, 10, "Teaching Experience", ln=True, align="C")
            self.pdf.ln(10)
            
            # Añadir fecha
            self.pdf.set_font("Arial", "I", 10)
            self.pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
            self.pdf.ln(10)
            
            # Añadir contenido
            self.pdf.set_font("Arial", "", 12)
            
            # Procesar cada fila
            for index, row in df.iterrows():
                logger.info(f"Procesando fila {index + 1}")
                
                # Añadir cada campo con su etiqueta en inglés
                for column in df.columns:
                    value = str(row[column])
                    if pd.notna(value) and value.strip():
                        # Sanitizar el texto
                        value = self._sanitize_text(value)
                        
                        # Traducir el nombre de la columna al inglés
                        column_en = self._translate_column_name(column)
                        self.pdf.set_font("Arial", "B", 12)
                        self.pdf.cell(0, 10, f"{column_en}:", ln=True)
                        self.pdf.set_font("Arial", "", 12)
                        self.pdf.multi_cell(0, 10, value)
                        self.pdf.ln(5)
                
                self.pdf.ln(10)
            
            # Guardar el PDF
            output_path = excel_path.replace('.xlsx', '_experience.pdf')
            logger.info(f"Guardando PDF en: {output_path}")
            self.pdf.output(output_path)
            
            # Verificar que el PDF se creó correctamente
            if not os.path.exists(output_path):
                raise Exception("No se pudo crear el archivo PDF")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error en generate_practicas_pdf: {str(e)}")
            raise
    
    def _translate_column_name(self, column: str) -> str:
        """
        Traduce el nombre de una columna al inglés
        
        Args:
            column: Nombre de la columna en español
            
        Returns:
            Nombre traducido al inglés
        """
        translations = {
            # Referentes
            "Nombre": "Name",
            "Email": "Email",
            "Teléfono": "Phone",
            "Cargo": "Position",
            "Institución": "Institution",
            "Dirección": "Address",
            "Ciudad": "City",
            "País": "Country",
            "Notas": "Notes",
            
            # Prácticas
            "Centro": "School",
            "Periodo": "Period",
            "Asignaturas": "Subjects",
            "Nivel": "Level",
            "Edades": "Age Range",
            "Horas": "Hours",
            "Responsabilidades": "Responsibilities",
            "Logros": "Achievements",
            "Evaluación": "Evaluation",
            "Observaciones": "Observations"
        }
        
        return translations.get(column, column)
    
    async def generate_application_form(self, offer: Dict, user_data: Dict) -> Optional[str]:
        """
        Genera un formulario de aplicación en PDF con solo los campos afirmativos y un diseño profesional.
        """
        try:
            logger.info(f"[PDF] Iniciando generación de application form para: {user_data.get('name')} - {offer.get('school_name')}")
            # Crear nombre único para el archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            school_name = offer['school_name'].replace(' ', '_').lower()
            filename = f"application_form_{school_name}_{timestamp}.pdf"
            filepath = os.path.join('temp', filename)
            logger.info(f"[PDF] Ruta destino: {filepath}")
            os.makedirs('temp', exist_ok=True)
            logger.info("[PDF] Directorio 'temp' verificado/creado")
            doc = SimpleDocTemplate(
                filepath,
                pagesize=letter,
                rightMargin=40,
                leftMargin=40,
                topMargin=50,
                bottomMargin=40
            )
            logger.info("[PDF] Documento PDF inicializado")
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=20,
                alignment=1,
                textColor=colors.HexColor('#2E4053')
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=13,
                spaceAfter=10,
                textColor=colors.HexColor('#154360')
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6
            )
            table_header_style = ParagraphStyle(
                'TableHeader',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.white,
                backColor=colors.HexColor('#2E4053'),
                alignment=1
            )
            # Contenido del documento
            content = []
            # Título
            content.append(Paragraph("Application Form", title_style))
            content.append(Spacer(1, 16))
            # Información de la posición
            content.append(Paragraph("Position Details", heading_style))
            position_data = [
                ["Position", offer.get('position', '')],
                ["School", offer.get('school_name', '')],
                ["Location", offer.get('location', '')],
                ["Closing Date", offer.get('closing_date', '')]
            ]
            position_table = Table(position_data, colWidths=[120, 320])
            position_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#D6DBDF')),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            content.append(position_table)
            content.append(Spacer(1, 14))
            # Información personal
            content.append(Paragraph("Personal Information", heading_style))
            personal_data = [
                ["Full Name", user_data.get('name', '')],
                ["Email Address", user_data.get('email', '')],
                ["Current Location", user_data.get('current_location', 'Ireland')],
                ["Visa Status", user_data.get('visa_status', 'Stamp 4')],
                ["Available to Start", user_data.get('available_to_start', 'Immediately')]
            ]
            personal_table = Table(personal_data, colWidths=[120, 320])
            personal_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#D6DBDF')),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            content.append(personal_table)
            content.append(Spacer(1, 14))
            # Solo mostrar respuestas afirmativas (Sí) en cualificaciones, excepto Teaching Council Registration
            content.append(Paragraph("Qualifications & Highlights", heading_style))
            highlights = []
            # if user_data.get('teaching_council_registration'):
            #     highlights.append(["Teaching Council Registration", "Yes"])
            if user_data.get('available_for_interview', True):
                highlights.append(["Available for Interview", "Yes"])
            if user_data.get('teaching_qualification', True):
                highlights.append(["Teaching Qualification", "Yes"])
            if user_data.get('garda_vetting', True):
                highlights.append(["Garda Vetting", "Yes"])
            if user_data.get('child_protection_training', True):
                highlights.append(["Child Protection Training", "Yes"])
            if user_data.get('first_aid_certification', True):
                highlights.append(["First Aid Certification", "Yes"])
            if user_data.get('special_education_training', True):
                highlights.append(["Special Education Training", "Yes"])
            if user_data.get('irish_language_proficiency', 'Basic') and user_data.get('irish_language_proficiency', '').lower() in ["intermedio", "avanzado", "advanced", "intermediate"]:
                highlights.append(["Irish Language Proficiency", user_data.get('irish_language_proficiency')])
            if highlights:
                highlights_table = Table(highlights, colWidths=[200, 240])
                highlights_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#D4EFDF')),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                content.append(highlights_table)
                content.append(Spacer(1, 14))
            # Declaración
            content.append(Paragraph("Declaration", heading_style))
            declaration_text = """
            I hereby declare that all the information provided in this application form is true and accurate to the best of my knowledge. I understand that any false or misleading information may result in the rejection of my application or dismissal if employed. I am available for interview and can start work as indicated above. I have all the necessary documentation to work in Ireland. I have completed all required training and hold all necessary certifications.
            """
            content.append(Paragraph(declaration_text, normal_style))
            content.append(Spacer(1, 12))
            # Firma
            content.append(Paragraph("Signature", heading_style))
            content.append(Spacer(1, 8))
            content.append(Paragraph("_________________________", normal_style))
            content.append(Paragraph("Date: _________________", normal_style))
            logger.info(f"[PDF] PDF generado correctamente en: {filepath}")
            doc.build(content)
            return filepath
        except Exception as e:
            logger.error(f"Error generando formulario de aplicación: {str(e)}")
            return None 