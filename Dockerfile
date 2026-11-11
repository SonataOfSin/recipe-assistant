FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt requirements-postgres.txt ./
RUN python -m pip install --no-cache-dir -r requirements-postgres.txt
COPY . .

EXPOSE 8000 8501
