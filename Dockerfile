FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/outputs /app/logs /app/memory

EXPOSE 8000

CMD ["uvicorn", "futures_research.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
