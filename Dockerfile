# Base stage for installing dependencies
FROM public.ecr.aws/lambda/python:3.11 AS base
WORKDIR /var/task

# Copy Pipfile and Pipfile.lock for dependency installation
COPY Pipfile Pipfile.lock ./

# Install pipenv
RUN pip install pipenv

# Copy the application code
COPY . .

# Development stage
FROM base AS dev
# Install all dependencies (including dev dependencies) for local testing
RUN pipenv install --ignore-pipfile
# Add the test_invoke.py script to the image
COPY tests/test_invoke.py .
ENTRYPOINT ["python3", "test_invoke.py"]

# Production stage
FROM base AS prod
# Install only production dependencies in system environment and remove pipenv
RUN pipenv install --deploy --ignore-pipfile --system && \
    pip uninstall -y pipenv
CMD ["main.lambda_handler"]
