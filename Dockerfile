FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RELAYDESK_HOME=/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY relaydesk ./relaydesk
RUN python -m pip install --no-cache-dir '.[api,postgres]' \
    && useradd --create-home --uid 10001 relaydesk \
    && mkdir -p /data \
    && chown relaydesk:relaydesk /data

USER relaydesk
EXPOSE 8013
CMD ["python", "-m", "uvicorn", "relaydesk.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8013"]
