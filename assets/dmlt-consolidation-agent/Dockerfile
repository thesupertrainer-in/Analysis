FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose agent port
EXPOSE 5000

# Start the agent
ENV PYTHONPATH=/app
CMD ["python", "-m", "uvicorn", "app.main:build_app", "--host", "0.0.0.0", "--port", "5000", "--factory"]
