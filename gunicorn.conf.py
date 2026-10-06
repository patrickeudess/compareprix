"""Configuration Gunicorn (production). Tout est surchargeable par variables d'environnement."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
# SQLite en mode WAL supporte plusieurs workers ; la limitation de débit est par worker (cf. README).
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '2'))
timeout = 30
graceful_timeout = 20
keepalive = 5
max_requests = 1000          # recyclage préventif des workers
max_requests_jitter = 100
accesslog = '-'              # journaux sur stdout/stderr (collectés par Docker)
errorlog = '-'
