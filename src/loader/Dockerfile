FROM python:3.11-slim AS builder

WORKDIR /app

# Install pipenv and dependencies
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
# Install dependencies only (no dev dependencies)
RUN pipenv install --deploy --system

# Copy shared library and application code
COPY src/shared /app/shared
COPY src/loader /app/loader

# Pre-download SentenceTransformer model to avoid runtime caching issues
# Set cache directories to /app/models which will be copied to runtime stage
ENV TRANSFORMERS_CACHE=/app/models/transformers
ENV HF_HOME=/app/models/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/models/sentence_transformers

# Create model cache directories
RUN mkdir -p /app/models/transformers /app/models/huggingface /app/models/sentence_transformers

# Pre-download the sentence-transformers model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

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

# Set cache environment variables to writable /tmp directory for Lambda runtime
ENV TRANSFORMERS_CACHE=/tmp/transformers
ENV HF_HOME=/tmp/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/sentence_transformers

# Set Lambda handler
CMD ["python", "-m", "awslambdaric", "loader.app.lambda_handler"]
