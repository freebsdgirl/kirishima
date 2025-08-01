FROM python:3.11

# Declare a build-time argument
ARG SERVICE_PORT

# Set an environment variable based on the build argument for runtime
ENV SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

# Install system dependencies needed for Consul (curl and unzip)
RUN apt-get update && \
    apt-get install -y curl gettext-base unzip && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY app/ ./app

# Expose the service port (for uvicorn)
EXPOSE ${SERVICE_PORT}

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use our custom entrypoint that starts Consul then uvicorn
ENTRYPOINT ["/entrypoint.sh"]
