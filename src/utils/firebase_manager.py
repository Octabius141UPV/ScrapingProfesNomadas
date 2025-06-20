import firebase_admin
from firebase_admin import credentials, firestore
import os

# Inicializar Firebase solo una vez
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")  # Cambia la ruta si tu JSON está en otro sitio
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_applied_vacancies(user_email):
    """Devuelve un set de IDs de vacantes ya aplicadas por el usuario."""
    ref = db.collection("aplicaciones").document(user_email).collection("vacantes")
    docs = ref.stream()
    return set(doc.id for doc in docs)

def mark_vacancy_as_applied(user_email, vacante_id, data=None):
    """Marca una vacante como aplicada para el usuario."""
    ref = db.collection("aplicaciones").document(user_email).collection("vacantes").document(vacante_id)
    ref.set(data or {"applied": True}) 