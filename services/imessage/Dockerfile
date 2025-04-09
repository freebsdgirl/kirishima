FROM python:3.11

# Declare a build-time argument
ARG SERVICE_PORT

# Set an environment variable based on the build argument for runtime
ENV SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

# EXPOSE uses the environment variable for documentation purposes.
EXPOSE ${SERVICE_PORT}

CMD ["sh", "-c", "uvicorn app.app:app --host 0.0.0.0 --port ${SERVICE_PORT} --reload"]

