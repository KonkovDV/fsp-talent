FROM node:20-bookworm-slim AS node

FROM python:3.12-slim-bookworm
# Only the node binary: no npm, no packages, nothing to install at run time.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY runner.py server.py harness.py harness.js ./
COPY tests ./tests
# The named volume takes this owner on first mount, so the unprivileged server can create its socket.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox \
    && mkdir -p /run/sandbox && chown sandbox /run/sandbox \
    && node --version
USER 10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD ["python", "server.py", "--health"]
CMD ["python", "server.py"]
