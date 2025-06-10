# Use an official Python image as the base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system tools, dependencies, and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nano \
    curl \
    wget \
    ca-certificates \
    libssl-dev \
    file \
    && pip install --no-cache-dir \
    requests \
    jsonschema \
    genson \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download ttyd (web terminal) binary
RUN wget -O /usr/local/bin/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 && \
    chmod +x /usr/local/bin/ttyd && \
    file /usr/local/bin/ttyd

# Create non-root user and group
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

# Set work directory
WORKDIR /app

# Copy files and set ownership
COPY --chown=appuser:appgroup report.py /app/

# Optionally create placeholder file
RUN echo "# Ready to run your Python API validator script" > validator.py

# Change to non-root user
USER appuser
# Expose port for ttyd
EXPOSE 8080

# Default command: Launch ttyd on port 8080 serving bash
CMD ["ttyd","-W", "--port", "8080", "bash"]
