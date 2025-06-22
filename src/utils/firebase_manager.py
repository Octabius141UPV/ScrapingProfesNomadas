import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import json
from dotenv import load_dotenv
import codecs

# Cargar variables de entorno y forzar la sobreescritura
load_dotenv(override=True)

try:
    # Método estándar y recomendado para inicializar Firebase
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not cred_path or not os.path.exists(cred_path):
        raise ValueError("La variable de entorno GOOGLE_APPLICATION_CREDENTIALS no está configurada o el archivo no existe. Debe apuntar a serviceAccountKey.json")

    cred = credentials.Certificate(cred_path)
    storage_bucket_url = os.getenv('FIREBASE_STORAGE_BUCKET')
    if not storage_bucket_url:
        raise ValueError("La variable de entorno FIREBASE_STORAGE_BUCKET no está configurada.")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'storageBucket': storage_bucket_url
        })
    
    db = firestore.client()
    bucket = storage.bucket()
    print("✅ Conexión con Firebase establecida correctamente.")

except Exception as e:
    print(f"❌ Error al inicializar Firebase: {e}")
    db = None
    bucket = None

def upload_file_to_storage(file_path: str, destination_blob_name: str) -> str:
    """
    Sube un archivo al bucket de Firebase Storage.

    Args:
        file_path: La ruta local del archivo a subir.
        destination_blob_name: El nombre que tendrá el archivo en el bucket.

    Returns:
        La URL pública del archivo subido.
    """
    if not bucket:
        print("❌ Bucket de Firebase Storage no está inicializado. No se puede subir el archivo.")
        return None
    try:
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(file_path)
        
        # Hacer el archivo públicamente accesible
        blob.make_public()
        
        print(f"✅ Archivo {file_path} subido a {destination_blob_name}.")
        return blob.public_url
    except Exception as e:
        print(f"❌ Error al subir el archivo a Firebase Storage: {e}")
        return None

def get_applied_vacancies(user_email):
    """Devuelve un set de IDs de vacantes ya aplicadas por el usuario."""
    ref = db.collection("aplicaciones").document(user_email).collection("vacantes")
    docs = ref.stream()
    return set(doc.id for doc in docs)

def mark_vacancy_as_applied(user_email, vacante_id, data=None):
    """Marca una vacante como aplicada para el usuario."""
    ref = db.collection("aplicaciones").document(user_email).collection("vacantes").document(vacante_id)
    ref.set(data or {"applied": True}) 