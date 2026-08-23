FROM python:3.11-slim

WORKDIR /app

# Ensure logs output directly without buffering
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY janitor.py .

# Safe default entrypoint running dry-run mode
ENTRYPOINT ["python", "janitor.py"]
CMD ["--dry-run"]