# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create and set working directory
WORKDIR /app

# Create golfcal2 user and group
RUN groupadd -r golfcal2 && useradd -r -g golfcal2 golfcal2 \
    && mkdir -p /var/lib/golfcal2/ics /var/log/golfcal2 \
    && chown -R golfcal2:golfcal2 /var/lib/golfcal2 /var/log/golfcal2 \
    && chmod 750 /var/lib/golfcal2 /var/log/golfcal2

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies and project
RUN pip install --no-cache-dir -e ".[dev]" \
    && chown -R golfcal2:golfcal2 /app

# Switch to non-root user
USER golfcal2

# Use tini as entrypoint
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["golfcal2-service"] 