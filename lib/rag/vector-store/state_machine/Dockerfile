# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11@sha256:6a842433a47c8e195a63232d108eb55e10fd87fbf9ff3b239b6260120e4bbbb3

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Install system dependencies and build tools
RUN yum update -y && \
    yum install -y gcc gcc-c++ make && \
    yum clean all

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the Lambda function code
COPY . .

# Set proper permissions
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["repository.state_machine.cleanup_repo_docs.lambda_handler"]
