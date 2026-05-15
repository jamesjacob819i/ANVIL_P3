FROM python:3.11-slim

WORKDIR /app

COPY services/triage_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/triage_worker/ .

CMD ["python", "worker.py"]
