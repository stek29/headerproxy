FROM python:3.13.0-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache -r requirements.txt

COPY main.py .
CMD ["python", "./main.py"]
