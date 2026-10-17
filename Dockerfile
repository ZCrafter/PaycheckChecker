FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Hours database and paystub PDFs live here; mount a dataset at /data
VOLUME /data
CMD ["python", "-m", "app.bot"]
