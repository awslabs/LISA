FROM public.ecr.aws/lambda/python:3.11@sha256:6a842433a47c8e195a63232d108eb55e10fd87fbf9ff3b239b6260120e4bbbb3

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Lambda function code
COPY . ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["repository.state_machine.cleanup_repo_docs.lambda_handler"]
