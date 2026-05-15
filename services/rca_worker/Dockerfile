FROM python:3.11-slim

WORKDIR /app

COPY services/rca_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY services/rca_worker/ .

CMD ["python", "worker.py"]
