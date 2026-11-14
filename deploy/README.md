# Voice and HTTPS deployment

Keep the existing .env and database directories. Copy individual missing settings
from .env.example; never overwrite database credentials or commit .env.

Local same-origin development:

```sh
docker compose -f docker-compose.yml -f compose.web.yml up --build -d
```

Open http://localhost:8080 (a browser microphone secure-context exception).
Do not open HTML with file:// or a separate static server: API URLs are relative.
Existing Neo4j bind mounts and loopback-only database ports are preserved.
Never run `down -v` or delete neo4j/data.

Production: provision a Linux Docker server and a domain, point DNS A (and AAAA
only when IPv6 works) at that server, allow inbound TCP 80/443, set SITE_ADDRESS
to the domain, set WEB_HTTP_BIND=0.0.0.0, WEB_HTTP_PORT=80,
WEB_HTTPS_BIND=0.0.0.0 and WEB_HTTPS_PORT=443, then run the same command.
Caddy obtains and renews certificates.
Do not expose 7475, 7688 or 8000 in cloud firewalls. Keep Caddy data volumes.
Public deployment has not been performed. Domain, server access and DNS remain
required. GitHub hosting does not run FastAPI.

POST /api/v1/audio/transcriptions accepts multipart field `file`, returns
`{"text":"English transcript"}`. Supports WebM, Ogg, MP4, WAV and MPEG audio.
Errors: 400 empty, 413 too large/long, 415 unsupported MIME, 422 decode failure,
429 busy, 503 model unavailable. Limits default to 10 MiB and 60 seconds.
The proxy also limits total request size. MIME is only an initial check; the
decoder validates content. Recordings are temporary and are not logged.

The local faster-whisper base.en model runs on CPU with int8; no paid API or key.
First request needs outbound model-download access and can take several minutes.
Models persist in speech-models, and one model instance is cached per process.
Use one worker; concurrent transcriptions get 429. Start with 2 CPU cores and
2–4 GiB available RAM, then measure actual workload. tiny.en reduces resource use.
The backend image includes no search vector assets: semantic search still needs
the existing project's embedding service/assets configured separately.

Smoke test: upload an English recording using the Swagger API or curl multipart;
check empty input, bad MIME and corrupt audio. Repeat valid uploads to check warm
model use. On each of Home, Gene Search, Trait Search, Literature and AI Assistant,
allow microphone, start/stop, verify editable text and no automatic submission.
Test HTTPS microphone permissions from the actual deployed domain.

If Neo4j already runs, start only the new services to avoid recreating it:

```sh
docker compose -f docker-compose.yml -f compose.web.yml config --quiet
docker compose -f docker-compose.yml -f compose.web.yml up --build -d --no-deps api web
```

This assumes the existing maizegene Compose network and Neo4j service exist.
No database operation or volume deletion is needed. Check chosen web ports are
free first. For a new installation use the first command at the top of this file.

Independent Windows Python test environment (requires installed Python 3.12):

```powershell
py -3.12 -m venv .test-venv
.\.test-venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.\.test-venv\Scripts\python.exe -m unittest backend.test_audio_service -v
.\.test-venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/site/ for same-origin development without Docker.
Contract tests use a stub model and do not prove speech recognition accuracy.
After downloading the model, upload real English audio twice and verify text
and warm model reuse. Original .venv is untouched.
