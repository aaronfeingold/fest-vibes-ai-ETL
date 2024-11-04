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
# Copy the test script
COPY tests/test_invoke.py .
# Set entrypoint for development/testing
ENTRYPOINT ["python3", "test_invoke.py"]

# Production stage
FROM base AS prod
# Set entrypoint for production
CMD ["main.lambda_handler"]
