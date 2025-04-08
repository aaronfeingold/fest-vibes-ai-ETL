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
# Set only non-sensitive environment variables
ENV BASE_URL=http://localhost:3000 \
    S3_BUCKET_NAME=ajf-live-re-wire-data-dev \
    REDIS_URL=host.docker.internal:6379

# Copy the test script
COPY tests/test_invoke.py .
# Set entrypoint for development/testing
ENTRYPOINT ["python3", "test_invoke.py"]

# Production stage
FROM base AS prod
# In production, all environment variables will be set by AWS Lambda
# No sensitive data in the Dockerfile
CMD ["main.lambda_handler"]
