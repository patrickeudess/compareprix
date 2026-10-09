FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# Utilisateur non-root sans shell
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Uniquement le nécessaire à l'exécution : pas de tests, pas de données d'exemple (data/ est exclu)
COPY app.py db.py pricing.py ratelimit.py uploads.py import_prices.py import_references.py merge_data.py \
     migrate_to_sqlite.py backup_db.py online_prices.py collaboration.py verification.py mailer.py gunicorn.conf.py ./
COPY templates templates
COPY static static
COPY config config

# /app/data = base SQLite, photos, sauvegardes : à monter sur un volume persistant
RUN mkdir -p /app/data && chown -R app:app /app/data
VOLUME /app/data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'), timeout=3)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
