ARG IMAGE=public.ecr.aws/sam/build-python3.11:latest
FROM $IMAGE

# Set home directory and pip config
ENV HOME="/tmp/home"
ENV PIP_CONFIG_FILE="/tmp/home/pip.conf"

# Set cache directories
ENV PIP_CACHE_DIR=/tmp/pip-cache
ENV POETRY_CACHE_DIR=/tmp/poetry-cache

# Setup directories and permissions first
RUN mkdir -p /tmp/home && \
    chmod -R 777 /tmp/home && \
    mkdir -p /tmp/pip-cache && \
    chmod -R 777 /tmp/pip-cache && \
    mkdir -p /tmp/poetry-cache && \
    chmod -R 777 /tmp/poetry-cache && \
    mkdir -p /usr/app && \
    chmod -R 777 /usr/app

# Add virtualenv path
ENV PATH="/usr/app/venv/bin:$PATH"

CMD [ "python" ]
