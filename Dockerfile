# Playwright's official Python image ships Chromium + all system libraries.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install chromium

COPY . .

# Container output is ephemeral; runs still write here during their lifetime.
RUN mkdir -p output

ENV HEADLESS=true \
    PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# IMPORTANT: a single worker — run state lives in this one process's memory,
# and the SSE stream must read the same job's progress queue.
# --timeout 0 so long research jobs are never killed mid-run.
CMD ["sh", "-c", "gunicorn webapp:app --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --worker-class gthread --timeout 0"]
