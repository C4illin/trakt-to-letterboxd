# Dockerfile with zendriver support for auto-import
FROM python:3.13-slim

WORKDIR /app

# Install Chromium (lighter than Google Chrome) and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Tell zendriver to use system Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV SCHEDULED=true
ENV IN_DOCKER=true

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY letterboxd_trakt/ letterboxd_trakt/
COPY healthcheck.py .

CMD ["python", "-u", "-m", "letterboxd_trakt.main"]
