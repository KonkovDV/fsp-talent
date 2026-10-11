FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Cyrillic in the candidate's PDF profile (fpdf2 embeds DejaVuSans.ttf). Only the core package, no fontconfig.
# The Debian mirror sometimes answers 500 (seen on a cold jury build): retry before failing the build.
RUN for i in 1 2 3 4 5; do \
        apt-get -o Acquire::Retries=3 update \
        && apt-get -o Acquire::Retries=3 install -y --no-install-recommends fonts-dejavu-core \
        && break; \
        echo "apt attempt $i failed, retrying" >&2; sleep $((i * 5)); \
    done \
    && test -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf \
    && rm -rf /var/lib/apt/lists/*
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
# Commit of the build, shown in /health (NEW-17). Last layer so a new commit does not bust the cache.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

CMD ["sh", "-c", "alembic upgrade head && python -m app.core.schema_sync && python -m app.core.rescore_stale && python -m app.core.app_login && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\""]
