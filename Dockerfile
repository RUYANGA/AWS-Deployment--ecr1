FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements/ requirements/
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x /app/scripts/entrypoint.sh \
    && useradd --create-home appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "--chdir", "src", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
