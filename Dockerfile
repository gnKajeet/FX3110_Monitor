FROM python:3.11-slim

# Install system dependencies (ping is in iputils-ping package)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    iputils-ping \
    openssh-client \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install (even though we don't need external packages)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY FX3110_Monitor.py .

# Create directory for logs
RUN mkdir -p /logs

# Run as non-root user for security
RUN useradd -m -u 1000 monitor && \
    chown -R monitor:monitor /app /logs
USER monitor

# Default command: run monitor and output to /logs
CMD ["sh", "-c", "python FX3110_Monitor.py > /logs/fx3110_log.tsv 2>&1"]
