# Use an official Python runtime as a parent image
FROM public.ecr.aws/lambda/python:3.11

# Set the working directory
WORKDIR /var/task

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install pipenv
RUN pip install pipenv

# Install dependencies using pipenv
RUN pipenv install --deploy --ignore-pipfile --system

# Copy the rest of the application code
COPY . .

# Command to run the Lambda function
CMD ["main.lambda_handler"]
