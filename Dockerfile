FROM public.ecr.aws/lambda/python:3.11

# Install pipenv
RUN pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ${LAMBDA_TASK_ROOT}/

# Install dependencies
WORKDIR ${LAMBDA_TASK_ROOT}
RUN pipenv install --deploy --system

# Copy function code
COPY main.py ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD [ "main.lambda_handler" ]
