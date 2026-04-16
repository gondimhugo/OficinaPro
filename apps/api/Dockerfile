FROM python:3.11-slim

WORKDIR /app

COPY apps/api /app

RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .[dev]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
