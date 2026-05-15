FROM python:3.11-slim

RUN apt-get update && apt-get install -y git docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/deployment_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/deployment_worker/ .

ENV PYTHONPATH=/app

CMD ["python", "worker.py"]
