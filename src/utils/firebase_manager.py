import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import json
from dotenv import load_dotenv
import codecs
from datetime import datetime, timedelta
import math

# Cargar variables de entorno y forzar la sobreescritura
load_dotenv(override=True)

try:
    # Método estándar y recomendado para inicializar Firebase
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not cred_path or not os.path.exists(cred_path):
        raise ValueError("La variable de entorno GOOGLE_APPLICATION_CREDENTIALS no está configurada o el archivo no existe. Debe apuntar a serviceAccountKey.json")

    cred = credentials.Certificate(cred_path)
    storage_bucket_url = os.getenv('FIREBASE_STORAGE_BUCKET')
    app_options = {'storageBucket': storage_bucket_url} if storage_bucket_url else {}
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, app_options)

    # Firestore protects application reservations; Storage remains optional.
    db = firestore.client()
    bucket = storage.bucket() if storage_bucket_url else None
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


def get_presentation_recipients(sender_email: str):
    """Devuelve un set de emails que ya recibieron la presentación para un remitente."""
    if not db or not sender_email:
        return set()
    ref = db.collection("presentaciones").document(sender_email).collection("destinatarios")
    docs = ref.stream()
    return set(doc.id for doc in docs)


def mark_presentation_sent(sender_email: str, recipient_email: str, data: dict = None):
    """Marca que un destinatario ya recibió la presentación desde un remitente."""
    if not db or not sender_email or not recipient_email:
        return
    payload = data or {}
    if "sent_at" not in payload:
        payload["sent_at"] = datetime.utcnow().isoformat()
    ref = db.collection("presentaciones").document(sender_email).collection("destinatarios").document(recipient_email)
    ref.set(payload)
# ---------------------------------------------------------------------------
# Atomic safety reservations for automated application emails.
# Document IDs are HMAC-derived pseudonyms supplied by application_send_policy;
# neither email address nor offer URL is stored in this collection.
# ---------------------------------------------------------------------------

APPLICATION_SEND_COLLECTION = "application_send_safety"
APPLICATION_SEND_QUEUE_COLLECTION = "application_send_queues"


def _snapshot_data(reference, transaction):
    snapshot = reference.get(transaction=transaction)
    if not getattr(snapshot, "exists", False):
        return {}
    return snapshot.to_dict() or {}


def _normalise_datetime(value, fallback):
    if isinstance(value, datetime):
        return value
    return fallback


def _reserve_application_send_transaction(
    transaction,
    account_ref,
    reservation_ref,
    *,
    daily_limit: int,
    min_interval_seconds: int,
    batch_limit: int,
    batch_pause_seconds: int,
    now: datetime,
):
    """Reserve one scheduled delivery slot using the caller's transaction.

    The daily document is selected only after calculating ``scheduled_at``. This
    prevents reservations made shortly before midnight from charging the wrong
    UTC day and lets every worker share the same batch/cooldown state.
    """
    reservation = _snapshot_data(reservation_ref, transaction)
    status = reservation.get("status")
    if status == "sent":
        return {"allowed": False, "reason": "duplicate_already_sent"}
    if status == "reserved":
        return {"allowed": False, "reason": "duplicate_pending_review"}

    account = _snapshot_data(account_ref, transaction)
    previous_slot = _normalise_datetime(account.get("next_available_at"), now)
    cooldown_until = _normalise_datetime(account.get("cooldown_until"), now)
    scheduled_at = max(now, previous_slot, cooldown_until)
    scheduled_day = scheduled_at.date().isoformat()
    daily_ref = account_ref.collection("days").document(scheduled_day)
    daily = _snapshot_data(daily_ref, transaction)
    sent_count = int(daily.get("sent_count", 0))
    pending_count = int(daily.get("pending_count", 0))
    if sent_count + pending_count >= daily_limit:
        return {"allowed": False, "reason": "daily_limit_reached"}

    batch_count = max(0, int(account.get("batch_count", 0)))
    if batch_count >= batch_limit:
        # ``scheduled_at`` already incorporates the previous batch cooldown.
        batch_count = 0
    batch_count += 1

    next_available_at = scheduled_at + timedelta(seconds=min_interval_seconds)
    next_cooldown_until = None
    if batch_count >= batch_limit:
        next_cooldown_until = scheduled_at + timedelta(seconds=batch_pause_seconds)
        next_available_at = max(next_available_at, next_cooldown_until)
    delay_seconds = max(0, math.ceil((scheduled_at - now).total_seconds()))

    transaction.set(
        reservation_ref,
        {
            "status": "reserved",
            "reserved_at": now,
            "scheduled_at": scheduled_at,
            "delivery_day": scheduled_day,
            "updated_at": now,
        },
        merge=True,
    )
    transaction.set(
        daily_ref,
        {
            "day": scheduled_day,
            "sent_count": sent_count,
            "pending_count": pending_count + 1,
            "updated_at": now,
        },
        merge=True,
    )
    transaction.set(
        account_ref,
        {
            "next_available_at": next_available_at,
            "batch_count": batch_count,
            "cooldown_until": next_cooldown_until,
            "updated_at": now,
        },
        merge=True,
    )
    return {
        "allowed": True,
        "reason": "reserved",
        "delay_seconds": delay_seconds,
    }


def _finalize_application_send_transaction(
    transaction, daily_ref, reservation_ref, *, now: datetime
):
    reservation = _snapshot_data(reservation_ref, transaction)
    if reservation.get("status") != "reserved":
        return {"reason": "reservation_not_pending"}

    daily = _snapshot_data(daily_ref, transaction)
    transaction.set(
        reservation_ref,
        {"status": "sent", "sent_at": now, "updated_at": now},
        merge=True,
    )
    transaction.set(
        daily_ref,
        {
            "sent_count": int(daily.get("sent_count", 0)) + 1,
            "pending_count": max(0, int(daily.get("pending_count", 0)) - 1),
            "updated_at": now,
        },
        merge=True,
    )
    return {"reason": "finalized"}


def _release_application_send_transaction(
    transaction,
    daily_ref,
    reservation_ref,
    *,
    now: datetime,
    error_category: str,
):
    reservation = _snapshot_data(reservation_ref, transaction)
    if reservation.get("status") != "reserved":
        return {"reason": "reservation_not_pending"}

    daily = _snapshot_data(daily_ref, transaction)
    transaction.set(
        reservation_ref,
        {
            "status": "released",
            "released_at": now,
            "updated_at": now,
            "release_category": error_category,
        },
        merge=True,
    )
    transaction.set(
        daily_ref,
        {
            "pending_count": max(0, int(daily.get("pending_count", 0)) - 1),
            "updated_at": now,
        },
        merge=True,
    )
    return {"reason": "released"}


def _application_send_references(account_id: str, offer_id: str):
    account_ref = db.collection(APPLICATION_SEND_COLLECTION).document(account_id)
    reservation_ref = account_ref.collection("reservations").document(offer_id)
    return account_ref, reservation_ref


def _application_send_account_and_reservation_references(account_id: str, offer_id: str):
    account_ref = db.collection(APPLICATION_SEND_COLLECTION).document(account_id)
    reservation_ref = account_ref.collection("reservations").document(offer_id)
    return account_ref, reservation_ref


def _reservation_daily_reference(account_ref, reservation):
    delivery_day = reservation.get("delivery_day") or reservation.get("reservation_day")
    if not isinstance(delivery_day, str) or not delivery_day:
        return None
    return account_ref.collection("days").document(delivery_day)


def reserve_application_send(
    account_id: str,
    offer_id: str,
    daily_limit: int,
    min_interval_seconds: int,
    batch_limit: int,
    batch_pause_seconds: int,
    now: datetime = None,
):
    """Atomically reserve a production email slot, failing closed on storage errors."""
    if not db:
        return {"allowed": False, "reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        account_ref, reservation_ref = _application_send_references(account_id, offer_id)
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            return _reserve_application_send_transaction(
                transaction,
                account_ref,
                reservation_ref,
                daily_limit=daily_limit,
                min_interval_seconds=min_interval_seconds,
                batch_limit=batch_limit,
                batch_pause_seconds=batch_pause_seconds,
                now=now,
            )

        return run(transaction)
    except Exception as exc:
        # Do not include identifiers or API error text in logs: those can contain PII.
        print("⚠️ No se pudo reservar un envío de aplicación (%s)." % type(exc).__name__)
        return {"allowed": False, "reason": "policy_store_unavailable"}


def finalize_application_send_reservation(
    account_id: str, offer_id: str, now: datetime = None
):
    """Mark a reserved slot as sent after SMTP accepts the message."""
    if not db:
        return {"reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        account_ref, reservation_ref = _application_send_account_and_reservation_references(
            account_id, offer_id
        )
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            reservation = _snapshot_data(reservation_ref, transaction)
            daily_ref = _reservation_daily_reference(account_ref, reservation)
            if daily_ref is None:
                return {"reason": "reservation_day_missing"}
            return _finalize_application_send_transaction(
                transaction, daily_ref, reservation_ref, now=now
            )

        return run(transaction)
    except Exception as exc:
        print("⚠️ No se pudo finalizar una reserva de envío (%s)." % type(exc).__name__)
        return {"reason": "policy_store_unavailable"}


def release_application_send_reservation(
    account_id: str,
    offer_id: str,
    now: datetime = None,
    error_category: str = "smtp_definite_failure",
):
    """Release a slot only when SMTP conclusively rejected the delivery."""
    if not db:
        return {"reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        account_ref, reservation_ref = _application_send_account_and_reservation_references(
            account_id, offer_id
        )
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            reservation = _snapshot_data(reservation_ref, transaction)
            daily_ref = _reservation_daily_reference(account_ref, reservation)
            if daily_ref is None:
                return {"reason": "reservation_day_missing"}
            return _release_application_send_transaction(
                transaction,
                daily_ref,
                reservation_ref,
                now=now,
                error_category=error_category,
            )

        return run(transaction)
    except Exception as exc:
        print("⚠️ No se pudo liberar una reserva de envío (%s)." % type(exc).__name__)
        return {"reason": "policy_store_unavailable"}


# ---------------------------------------------------------------------------
# Persistent queue metadata for automated application delivery.
#
# Queue documents deliberately contain only HMAC-derived account, vacancy, and
# position identifiers plus lifecycle metadata. Credentials, recipients, mail
# text, and files stay in the authenticated in-memory delivery session.
# ---------------------------------------------------------------------------

_QUEUE_TERMINAL_STATUSES = {
    "sent",
    "failed_definite",
    "blocked_ambiguous",
    "deduplicated",
}


def _application_send_queue_reference(account_id: str, offer_id: str):
    account_ref = db.collection(APPLICATION_SEND_QUEUE_COLLECTION).document(account_id)
    return account_ref.collection("items").document(offer_id)


def _enqueue_application_send_queue_item_transaction(
    transaction,
    queue_ref,
    *,
    run_id: str,
    position_id: str,
    now: datetime,
):
    """Create or safely re-bind an in-memory delivery session to one item."""
    item = _snapshot_data(queue_ref, transaction)
    status = item.get("status")
    if status == "sent":
        return {"queued": False, "reason": "duplicate_already_sent"}
    if status in {"processing", "blocked_ambiguous"}:
        return {"queued": False, "reason": "duplicate_pending_review"}
    if status == "queued":
        transaction.set(
            queue_ref,
            {"last_run_id": run_id, "updated_at": now},
            merge=True,
        )
        return {"queued": True, "reason": "queue_existing"}

    # A previously definite failure or daily-limit deferral is safe to bind to
    # a newly authenticated in-memory session. No SMTP retry happens merely
    # because the process restarted.
    transaction.set(
        queue_ref,
        {
            "status": "queued",
            "queued_at": item.get("queued_at", now),
            "updated_at": now,
            "run_id": run_id,
            "last_run_id": run_id,
            "position_id": position_id,
            "batch_number": None,
            "last_error_category": None,
        },
        merge=True,
    )
    return {"queued": True, "reason": "queued" if not item else "queue_rebound"}


def _claim_application_send_queue_item_transaction(
    transaction,
    queue_ref,
    *,
    run_id: str,
    batch_number: int,
    now: datetime,
):
    """Claim one queued item before starting local SMTP preparation."""
    item = _snapshot_data(queue_ref, transaction)
    if item.get("status") != "queued":
        return {
            "claimed": False,
            "reason": "queue_item_not_available",
            "status": item.get("status", "missing"),
        }
    transaction.set(
        queue_ref,
        {
            "status": "processing",
            "run_id": run_id,
            "batch_number": batch_number,
            "claimed_at": now,
            "updated_at": now,
        },
        merge=True,
    )
    return {"claimed": True, "reason": "claimed"}


def _set_application_send_queue_item_status_transaction(
    transaction,
    queue_ref,
    *,
    status: str,
    now: datetime,
    reason: str = None,
    error_category: str = None,
):
    """Set an allow-listed queue state after a local delivery attempt."""
    if status not in _QUEUE_TERMINAL_STATUSES | {"queued"}:
        raise ValueError("Unsupported queue status")
    item = _snapshot_data(queue_ref, transaction)
    if not item:
        return {"reason": "queue_item_missing"}
    payload = {
        "status": status,
        "updated_at": now,
        "last_decision": reason,
        "last_error_category": error_category,
    }
    if status == "queued":
        payload["deferred_at"] = now
    else:
        payload["completed_at"] = now
    transaction.set(queue_ref, payload, merge=True)
    return {"reason": "queue_item_updated", "status": status}


def enqueue_application_send_queue_item(
    account_id: str,
    offer_id: str,
    run_id: str,
    position_id: str,
    now: datetime = None,
):
    """Persist non-sensitive queue metadata before an authenticated session sends."""
    if not db:
        return {"queued": False, "reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        queue_ref = _application_send_queue_reference(account_id, offer_id)
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            return _enqueue_application_send_queue_item_transaction(
                transaction,
                queue_ref,
                run_id=run_id,
                position_id=position_id,
                now=now,
            )

        return run(transaction)
    except Exception as exc:
        print("⚠️ No se pudo encolar una solicitud (%s)." % type(exc).__name__)
        return {"queued": False, "reason": "policy_store_unavailable"}


def claim_application_send_queue_item(
    account_id: str,
    offer_id: str,
    run_id: str,
    batch_number: int,
    now: datetime = None,
):
    """Atomically make one queue item active for the current local session."""
    if not db:
        return {"claimed": False, "reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        queue_ref = _application_send_queue_reference(account_id, offer_id)
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            return _claim_application_send_queue_item_transaction(
                transaction,
                queue_ref,
                run_id=run_id,
                batch_number=batch_number,
                now=now,
            )

        return run(transaction)
    except Exception as exc:
        print("⚠️ No se pudo reclamar una solicitud en cola (%s)." % type(exc).__name__)
        return {"claimed": False, "reason": "policy_store_unavailable"}


def set_application_send_queue_item_status(
    account_id: str,
    offer_id: str,
    status: str,
    now: datetime = None,
    reason: str = None,
    error_category: str = None,
):
    """Persist a safe queue transition without retaining SMTP material."""
    if not db:
        return {"reason": "policy_store_unavailable"}
    now = now or datetime.utcnow()
    try:
        queue_ref = _application_send_queue_reference(account_id, offer_id)
        transaction = db.transaction()

        @firestore.transactional
        def run(transaction):
            return _set_application_send_queue_item_status_transaction(
                transaction,
                queue_ref,
                status=status,
                now=now,
                reason=reason,
                error_category=error_category,
            )

        return run(transaction)
    except Exception as exc:
        print("⚠️ No se pudo actualizar una solicitud en cola (%s)." % type(exc).__name__)
        return {"reason": "policy_store_unavailable"}
