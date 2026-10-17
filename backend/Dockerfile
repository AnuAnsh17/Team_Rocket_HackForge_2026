# Proofline backend image.
#
# Multi-stage is intentionally not used: there are no compiled assets, and a single
# stage keeps the build fast for a small team. The runtime stage still drops privileges.

FROM python:3.14-slim

# Keep Python predictable inside the container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies before copying source, so a code change does not invalidate the
# dependency layer.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

# Application source. .dockerignore keeps .env, tests output and receipt storage out.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# Run as an unprivileged user. A receipt-processing service should never be root.
RUN useradd --create-home --uid 10001 proofline \
    && mkdir -p /app/.local-storage/receipts \
    && chown -R proofline:proofline /app
USER proofline

EXPOSE 8000

# No curl in the image; use Python for the health probe so the check needs no extra tool.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

# Migrations are NOT run here on purpose: applying schema changes automatically on
# container start is how a bad migration takes down a service with no review step.
# Run `alembic upgrade head` as an explicit deploy step.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
