# Automated email delivery: safety and audit operations

This project keeps automatic SMTP delivery. It now persists a per-client-Gmail
queue and assigns every production send a persistent, atomic reservation before
Gmail is contacted. The controls are **fail-closed by default**: a production
email is not sent when the reservation store or pseudonymization secret is
unavailable.

## Configure the safety controls

Set these variables in the deployed `.env` (do not commit the real file):

```env
APPLICATION_AUDIT_HASH_KEY=<at-least-32-random-characters>
APPLICATION_SEND_DAILY_LIMIT=100
APPLICATION_SEND_BATCH_LIMIT=10
APPLICATION_SEND_MIN_INTERVAL_SECONDS=10
APPLICATION_SEND_BATCH_PAUSE_SECONDS=300
```

These are a production safety contract, not throughput tuning: the daily and
batch values are upper ceilings (values above 100 and 10 are clamped), while the
spacing and pause values are lower floors (values below 10 and 300 seconds are
clamped). More restrictive daily/batch values remain valid. Fast values are
accepted only with the explicit non-production configuration
`APPLICATION_AUDIT_ENVIRONMENT=test` in an isolated test process; there is no
runtime environment-variable escape hatch for a deployed bot.

`APPLICATION_AUDIT_HASH_KEY` is mandatory for production sending. It must
contain at least 32 cryptographically random characters;
empty, short, and known placeholder values are rejected. It creates HMAC
identifiers for accounts, recipients, and offers; raw
email addresses and offer URLs are not used in the new safety collection or
structured audit events. Use one stable secret per environment. Rotating it
changes identifiers and therefore starts a fresh deduplication namespace.

The daily allowance is a UTC daily window and is charged to the reservation's
**scheduled SMTP delivery date**, not the earlier queue/enqueue date. The worker
sends **10** emails sequentially, waits **10 seconds** between allocated sends,
pauses **300 seconds** after each batch, and automatically starts the next batch
until the queue is empty or the daily maximum is reached. Firestore atomically
persists each account's next slot, batch count, and cooldown, so concurrent bot
processes collectively cannot create an eleventh delivery slot before the
five-minute pause. A duplicate sent offer is skipped; a duplicate reservation with
an indeterminate SMTP result remains locked for review rather than risking a
second email.

### Queue lifecycle and restart semantics

For production, each candidate is first written to
`application_send_queues/{hmac-account}/items/{hmac-vacancy}`. This document
contains only HMAC account/vacancy/position IDs, run and batch IDs, timestamps,
state, and an error category. It never contains a recipient address, App Password,
email subject/body, attachment name/content, CV, or generated document.

1. A queued item is atomically claimed by the current authenticated delivery
   session.
2. The SMTP reservation is made immediately before local message construction.
   Its scheduled UTC delivery day is atomically charged against that day's
   allowance, even if the reservation was requested before midnight.
3. SMTP acceptance makes the reservation and queue item `sent`.
4. A known pre-send failure (for example authentication or recipient rejection)
   releases the reservation and records `failed_definite`; an authentication
   failure stops the current run instead of repeating it for every offer.
5. A network or ambiguous SMTP result remains `blocked_ambiguous` with its
   reservation locked; it is never auto-retried.
6. At the UTC daily cap, the current and later items stay `queued` for another
   authenticated session.

Known failures still consume their already allocated cadence slot. Although their
daily reservation is released because no message was delivered, keeping the slot
in the persistent batch counter prevents concurrent retry workers from turning a
failure burst into rapid SMTP traffic.

The queue survives process restarts, but **full autonomous SMTP resumption after
a restart is intentionally not possible**: the bot does not persist the App
Password, email body, attachment paths, or document contents. A restarted process
can re-bind still-queued HMAC vacancy records only when the client has again
provided an authenticated in-memory session and the required local documents are
available. Items that were `processing` or `blocked_ambiguous` at a crash remain
locked for review because sending them again could duplicate an email. Fully
autonomous restart delivery would require a separate secure secret manager,
encrypted durable document storage, short-lived access tokens, access controls,
and a documented consent/retention model; this project deliberately does not fake
that by storing an App Password in Firestore.

A rejected recipient or failed SMTP authentication is known not to have sent the
message, so its reservation is released. Network and generic SMTP failures are
indeterminate and intentionally remain reserved. This is a safety trade-off:
check the sender's Gmail **Sent** folder and the audit event before any manual
retry. There is no automatic retry for an indeterminate result.

Test-mode emails do not create production queue records, reserve a production
slot, affect the daily allowance, or create production deduplication records.
They **still chain through the local batch ceiling, spacing, and batch pause** to
prevent a test command from flooding the test inbox. Production timing is
persisted across bot processes; test-mode timing is intentionally local because it
creates no production state. This applies both to the Telegram `/test` flow and
`scripts/scrape_all_safe.py`'s test-email branch.

## Google Cloud Logging (optional, no configuration is performed by the code)

Install dependencies and set:

```env
GOOGLE_CLOUD_AUDIT_LOGGING_ENABLED=true
GOOGLE_CLOUD_PROJECT=<target-project-id>
GOOGLE_CLOUD_AUDIT_LOG_NAME=profes_nomadas_application_audit
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
```

Before enabling it, an administrator must:

1. Enable **Cloud Logging API** in `GOOGLE_CLOUD_PROJECT`.
2. Grant the service account in `GOOGLE_APPLICATION_CREDENTIALS` the project role
   **`roles/logging.logWriter`**.
3. Ensure that the same credentials can access the existing Firestore project used
   for the reservations. No Firebase or GCP resources are created by this change.
4. Run `pip install -r requirements.txt` so `google-cloud-logging` is available.

Cloud Logging is opt-in. Initialization and write failures are non-fatal: the bot
continues with standard local structured logs and does not expose credentials or
message contents in the error.

The log payload contains only run ID, HMAC account/recipient/offer/position IDs,
queue and batch metadata, counts, outcome, error category, environment, an
optional deployment label, and rate/dedup decision. It never
contains an App Password, raw email address, subject, body, attachment name or
file, CV, or any other document contents.

`host` is omitted unless `APPLICATION_AUDIT_HOST` is explicitly set to a
non-personal deployment label such as `prod-worker-eu-1`; the code never falls
back to the local machine hostname.

Use this safe Logs Explorer query (replace the project and log name if changed):

```text
logName="projects/PROJECT_ID/logs/profes_nomadas_application_audit"
jsonPayload.event_type=("application_send_run_started" OR "application_send_queue_enqueued" OR "application_send_queue_transition" OR "application_send_batch_paused" OR "application_smtp_result" OR "application_send_run_completed")
```

To investigate a run, add `jsonPayload.run_id="<run-id>"`. To find failures,
add `jsonPayload.outcome="failed"` or inspect `jsonPayload.error_category`. The
query uses IDs and categories, not customer information.

## Gmail App Passwords and OAuth

An App Password is a Gmail credential that bypasses the normal interactive login
for a specific application. If SMTP must remain automated, each client should
create a **separate, clearly labelled** App Password in their Google Account,
for example `Profes Nomadas 2026-08`, and provide only that 16-character password
to the bot. Do not use the main Google Account password.

Revoking that labelled App Password in the client's Google Account invalidates
only that credential. The bot will immediately be unable to authenticate with
it and future automated SMTP sends will fail until the client creates and
supplies a new App Password. Revocation is appropriate after an incident, when a
client leaves, or whenever credential exposure is suspected.

Google's preferred model for third-party access is OAuth 2.0 / Sign in with
Google, using narrowly scoped, revocable tokens rather than a stored password.
For Gmail sending that means an OAuth-authorized flow (such as Gmail API or SMTP
with XOAUTH2), not storing an App Password. OAuth improves credential security,
revocation, and auditing; **it does not make unlimited or abusive automated mail
acceptable**. The rate limits, deduplication, spacing, and honest recipient
behavior still apply.
