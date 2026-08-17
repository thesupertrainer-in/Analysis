FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
#
# This includes app/excel_generator/, which the Excel tool launches as a
# subprocess. asset.yaml builds with buildPath ".", so the build context is
# this directory only — the generator has to live under app/ to reach the
# image at all. Do not move it back out to a sibling directory.
COPY app/ ./app/

# Fail the build rather than the deployment if the generator is missing.
RUN test -f /app/app/excel_generator/generate_report.py \
    && test -f /app/app/calc_engine.py \
    && python -c "import openpyxl; print('openpyxl', openpyxl.__version__)"

# Expose agent port
EXPOSE 5000

# Start the agent
ENV PYTHONPATH=/app
CMD ["python", "-m", "uvicorn", "app.main:build_app", "--host", "0.0.0.0", "--port", "5000", "--factory"]
