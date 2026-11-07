# REVIEW ONLY: a separate operator-only executor, never the API container.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
WORKDIR /opt/personal-codex
COPY app/isolation.py app/secure_files.py app/security.py ./app/
COPY scripts/isolated_executor.py ./scripts/isolated_executor.py
USER 65534:65534
ENTRYPOINT ["/usr/local/bin/python3", "/opt/personal-codex/scripts/isolated_executor.py"]
