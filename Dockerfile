# ---------- Base layer: shared setup ----------
FROM public.ecr.aws/lambda/python:3.11 AS base
WORKDIR /var/task

# Install pipenv and copy lockfiles
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./

# ---------- Dev layer: includes dev deps ----------
FROM base AS dev

# Install dev dependencies into system environment (from Pipfile.lock)
RUN pipenv install --dev --deploy --system

# Remove pipenv (not needed at runtime)
RUN pip uninstall -y pipenv

# Copy full application
COPY . .

# Set development environment variables
ENV BASE_URL=http://localhost:3000 \
    S3_BUCKET_NAME=ajf-live-re-wire-data-dev \
    REDIS_URL=host.docker.internal:6379

# Entrypoint for local testing
COPY tests/test_invoke.py .
ENTRYPOINT ["python3", "test_invoke.py"]

# ---------- Prod layer: only prod deps ----------
FROM base AS prod

# Install ONLY prod dependencies into system environment (from Pipfile.lock)
RUN pipenv install --deploy --system --ignore-pipfile

# Remove pipenv
RUN pip uninstall -y pipenv

# Copy app code (don't copy dev/test stuff)
COPY . .

# AWS Lambda runtime entry point
CMD ["main.lambda_handler"]
