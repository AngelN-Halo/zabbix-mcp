FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 mcp

COPY --chown=mcp:mcp config.py groups.py zabbix_client.py status_service.py server.py ./
COPY --chown=mcp:mcp scripts ./scripts

USER mcp

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
