#!/bin/sh
set -e

# If a Consul service template exists, substitute environment variables to generate the actual config file.
if [ -f /consul/config/api-service.json.template ]; then
    envsubst < /consul/config/api-service.json.template > /consul/config/api-service.json
fi

# Start the Consul agent in the background.
# This binds to the primary IP and retries joining the cluster using the hostname "consul".
consul agent \
  -bind=$(hostname -I | awk '{print $1}') \
  -retry-join=consul \
  -client=0.0.0.0 \
  -data-dir=/consul-data \
  -config-dir=/consul/config \
  &

# Give Consul a moment to initialize
sleep 2

# Start uvicorn with the same command you had in CMD
exec uvicorn app.app:app --host 0.0.0.0 --port ${SERVICE_PORT} --reload
