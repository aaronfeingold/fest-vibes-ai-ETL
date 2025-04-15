FROM python:3.10-slim as builder

WORKDIR /app

# Install poetry and dependencies
RUN pip install poetry
COPY pyproject.toml ./
# Configure poetry to not use virtualenvs since we're in a container
RUN poetry config virtualenvs.create false
# Install dependencies only (no dev dependencies)
RUN poetry install --no-dev

# Copy shared library and application code
COPY src/shared /app/shared
COPY src/scraper /app/scraper

# Second stage: runtime
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages and app code from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app /app

# Set Python path to include app directory
ENV PYTHONPATH=/app

# Set Lambda handler
CMD ["python", "-m", "awslambdaric", "scraper.app.lambda_handler"]
