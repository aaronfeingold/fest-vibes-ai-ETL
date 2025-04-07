# Base stage for installing dependencies
FROM public.ecr.aws/lambda/python:3.11 AS base
WORKDIR /var/task

# Copy Pipfile and Pipfile.lock for dependency installation
COPY Pipfile Pipfile.lock ./

# Install pipenv
RUN pip install pipenv

# Install dependencies in system environment to avoid duplication across stages
RUN pipenv install --ignore-pipfile --system
# Uninstall pipenv after dependencies are installed
RUN pip uninstall -y pipenv
# Copy the application code (done once here to avoid repeating in stages)
COPY . .

# Development stage
FROM base AS dev
# Set environment variables for local development with placeholders
ENV PG_DATABASE_URL=postgresql://aaronfeingold@host.docker.internal:5432/ajf_dev \
    BASE_URL=http://localhost:3000 \
    GOOGLE_MAPS_API_KEY="" \
    S3_BUCKET_NAME=ajf-live-re-wire-data-dev

# Copy the test script
COPY tests/test_invoke.py .
# Set entrypoint for development/testing
ENTRYPOINT ["python3", "test_invoke.py"]

# Production stage
FROM base AS prod
# In production, these will be set by AWS Lambda environment variables
# Sensitive values should be retrieved from AWS Secrets Manager
ENV PG_DATABASE_URL="" \
    BASE_URL="" \
    GOOGLE_MAPS_API_KEY="" \
    S3_BUCKET_NAME=""

# Set entrypoint for production
CMD ["main.lambda_handler"]
