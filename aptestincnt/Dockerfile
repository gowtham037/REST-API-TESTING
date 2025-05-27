# Use an official Python image as the base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system tools and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nano \
    curl \
    && pip install --no-cache-dir \
    requests \
    jsonschema \
    genson \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Optionally create placeholder file (not mandatory)
RUN echo "# Ready to run your Python API validator script" > validator.py

# Default command drops into shell or Python interpreter
CMD ["python"]
