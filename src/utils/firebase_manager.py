import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import json
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

try:
    # Construir el diccionario de credenciales a partir de variables de entorno individuales
    private_key_from_env = os.getenv('FIREBASE_PRIVATE_KEY', '')
    
    # Es crucial reemplazar los caracteres de escape '\\n' por saltos de línea reales '\n'
    private_key = private_key_from_env.replace('\\n', '\n')

    creds_dict = {
        "type": os.getenv("FIREBASE_TYPE"),
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": private_key,
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN")
    }

    if not all(creds_dict.values()):
        raise ValueError("Faltan una o más variables de entorno de Firebase. Asegúrate de que todas las variables FIREBASE_* están configuradas en el archivo .env")

    cred = credentials.Certificate(creds_dict)
    storage_bucket_url = os.getenv('FIREBASE_STORAGE_BUCKET')
    if not storage_bucket_url:
        raise ValueError("La variable de entorno FIREBASE_STORAGE_BUCKET no está configurada.")

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