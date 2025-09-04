FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install component-specific dependencies
COPY src/cache_manager/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library and application code
COPY src/shared /app/shared
COPY src/cache_manager /app/cache_manager

# Second stage: runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and app code from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Set Python path to include app directory
ENV PYTHONPATH=/app

# Set Lambda handler
CMD ["python", "-m", "awslambdaric", "cache_manager.app.lambda_handler"]
