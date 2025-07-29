FROM python:3.11-slim AS builder

WORKDIR /app

# Install pipenv and dependencies
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
# Install dependencies only (no dev dependencies)
RUN pipenv install --deploy --system

# Copy shared library and application code
COPY src/shared /app/shared
COPY src/cache_manager /app/cache_manager

# Second stage: runtime
FROM python:3.11-slim

WORKDIR /app

# Install PostgreSQL client and build tools for psycopg2
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and app code from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Set Python path to include app directory
ENV PYTHONPATH=/app

# Set Lambda handler
CMD ["python", "-m", "awslambdaric", "cache_manager.app.lambda_handler"]
