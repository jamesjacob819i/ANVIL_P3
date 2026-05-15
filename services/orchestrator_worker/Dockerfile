FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY services/orchestrator_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/orchestrator_worker/ .

CMD ["python", "worker.py"]
