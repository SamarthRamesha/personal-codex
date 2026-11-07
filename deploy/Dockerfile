# PREPARATION ONLY. Review and approve an exact official Python image digest.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/personal-codex
COPY app/ ./app/
COPY web/ ./web/
COPY scripts/restore_database.py ./scripts/restore_database.py
# Compose supplies an approved numeric non-root UID/GID. No packages or Git installed.
USER 65534:65534
CMD ["python3", "-m", "app.server"]
