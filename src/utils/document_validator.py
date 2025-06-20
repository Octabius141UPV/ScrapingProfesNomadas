#!/usr/bin/env python3
"""
Validador de documentos Excel
"""

import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DocumentValidator:
    def __init__(self):
        """
        Inicializa el validador de documentos
        """
        self.referentes_template = 'data/Contactos de Referentes.xlsx'
        self.practicas_template = 'data/practicasPlantilla.xlsx'
        
    def validate_document(self, file_path: str) -> tuple[bool, str]:
        """
        Valida que el documento Excel tenga la estructura correcta
        
        Args:
            file_path: Ruta al archivo Excel a validar
            
        Returns:
            tuple[bool, str]: (es_válido, mensaje)
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                return False, "El archivo no existe"
                
            # Leer el archivo Excel
            df = pd.read_excel(file_path)
            
            # Verificar que no esté vacío
            if df.empty:
                return False, "El archivo Excel está vacío"
                
            # Verificar si es un archivo de referentes
            if os.path.exists(self.referentes_template):
                if self._validate_structure(df, self.referentes_template):
                    return True, "Archivo de referentes válido"
                    
            # Verificar si es un archivo de prácticas
            if os.path.exists(self.practicas_template):
                if self._validate_structure(df, self.practicas_template):
                    return True, "Archivo de prácticas válido"
                    
            return False, "El archivo Excel no tiene la estructura correcta. Debe seguir el formato de 'Contactos de Referentes.xlsx' o 'practicasPlantilla.xlsx'"
            
        except Exception as e:
            logger.error(f"Error validando documento: {str(e)}")
            return False, f"Error validando el documento: {str(e)}"
            
    def _validate_structure(self, df: pd.DataFrame, template_path: str) -> bool:
        """
        Valida que el DataFrame tenga la misma estructura que la plantilla
        
        Args:
            df: DataFrame a validar
            template_path: Ruta a la plantilla
            
        Returns:
            bool: True si la estructura es válida
        """
        try:
            # Leer la plantilla
            template_df = pd.read_excel(template_path)
            
            # Verificar que tengan las mismas columnas
            if set(df.columns) != set(template_df.columns):
                return False
                
            # Verificar que no haya columnas vacías
            for column in df.columns:
                if df[column].isna().all():
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error validando estructura: {str(e)}")
            return False 