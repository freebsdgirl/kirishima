FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# Declare a build-time argument
ARG SERVICE_PORT

# Set an environment variable based on the build argument for runtime
ENV SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

# Install system dependencies 
RUN apt-get update && \
    apt-get install -y curl gettext-base unzip libasound2 libportaudio2 alsa-utils pulseaudio-utils build-essential python3-dev portaudio19-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY app/ ./app

# Expose the service port (for uvicorn)
EXPOSE ${SERVICE_PORT}

# Copy the entrypoint script and make it executableoh 
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /app/cache && chmod -R 777 /app/cache

# Use our custom entrypoint that starts Consul then uvicorn
ENTRYPOINT ["/entrypoint.sh"]
