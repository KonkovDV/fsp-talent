FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir ".[test]"
COPY alembic.ini .
COPY alembic ./alembic
COPY seed ./seed
COPY tests ./tests
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /secrets && chown appuser /secrets
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=8 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
