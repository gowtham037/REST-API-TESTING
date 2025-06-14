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
    tzdata \
    && pip install --no-cache-dir \
    requests \
    jsonschema \
    genson \
    pytz \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Download ttyd (web terminal) binary
RUN wget -O /usr/local/bin/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 && \
    chmod +x /usr/local/bin/ttyd && \
    file /usr/local/bin/ttyd

# Create non-root user and group with home directory and bash shell
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /home/appuser --shell /bin/bash appuser && \
    mkdir -p /home/appuser && \
    chown appuser:appgroup /home/appuser

# Set custom prompt
RUN echo 'export PS1="Rest_API_Testing@\\h:\\w\\$ "' >> /home/appuser/.bashrc && \
    chown appuser:appgroup /home/appuser/.bashrc

# Set working directory
WORKDIR /app

# Copy Python scripts and assign ownership
COPY --chown=appuser:appgroup report.py /app/
COPY --chown=appuser:appgroup validate_api.py /app/
COPY --chown=appuser:appgroup ai.py /app/

# Optional placeholder file
RUN echo "# Ready to run your Python API validator script" > validator.py

# Use non-root user
USER appuser

# Expose ttyd port
EXPOSE 8080

# Start ttyd bash shell with custom prompt
CMD ["ttyd", "-W", "--port", "8080", "bash"]
