# vibe-coded development dockerfile, please do not use in production, pleaaase
# this is held together by hopes and dreams
FROM python:3.14.8-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY manage.py .
COPY sode/ sode/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
