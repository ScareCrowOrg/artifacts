FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# Copy job-types definitions (required by dynamic config loader)
COPY ../../../job-types /app/artifacts/canonical/job-types

CMD ["python", "main.py"]
