# Use an official Python runtime as a parent image
FROM public.ecr.aws/lambda/python:3.11

# Set the working directory
WORKDIR /var/task

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install pipenv and dependencies in the global system, then remove pipenv
RUN pip install pipenv && \
    pipenv install --deploy --ignore-pipfile --system && \
    pip uninstall -y pipenv

# Copy the rest of the application code
COPY . .

# Add the test_invoke.py script to the image
COPY tests/test_invoke.py .

# Use the Lambda handler for actual deployments
CMD ["main.lambda_handler"]

# To test locally, override CMD to run the test script
ARG ENVIRONMENT=dev
ENTRYPOINT ["python3", "test_invoke.py"]
