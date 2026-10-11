FROM node:20-bookworm-slim AS node

FROM python:3.12-slim-bookworm
# Only the node binary: no npm, no packages, nothing to install at run time.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY runner.py server.py harness.py harness.js harness_sql.py ./
COPY tests ./tests
# The named volume takes this owner on first mount, so the unprivileged server can create its socket.
# gid 10001 is fixed: the API container joins it (group_add) to reach the 0660 socket.
RUN groupadd --gid 10001 sandbox \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin sandbox \
    && mkdir -p /run/sandbox && chown sandbox:sandbox /run/sandbox \
    && node --version
USER 10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD ["python", "server.py", "--health"]
CMD ["python", "server.py"]
