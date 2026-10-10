FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml requirements.lock ./
COPY app ./app
# requirements.lock pins the versions the test suite passed on, so a rebuild months later gets the same stack.
# The pair model is a local extra. The jury stand is a CPU machine with 8 GB, so its image skips it.
ARG INSTALL_RERANKER=0
RUN pip install --no-cache-dir -c requirements.lock ".[test]" \
    && if [ "$INSTALL_RERANKER" = "1" ]; then pip install --no-cache-dir sentence-transformers; fi
COPY alembic.ini .
COPY alembic ./alembic
COPY seed ./seed
COPY tests ./tests
COPY docker-entrypoint.sh /entrypoint.sh
# A checkout on Windows stores CR. The kernel then cannot run the script.
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod +x /entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /secrets && chown appuser /secrets
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=8 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && python -m app.core.schema_sync && python -m app.core.app_login && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\""]
