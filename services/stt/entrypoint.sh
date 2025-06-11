#!/bin/sh
set -e

# If a Consul service template exists, substitute environment variables to generate the actual config file.
#if [ -f /consul/config/stt-service.json.template ]; then
#    envsubst < /consul/config/stt-service.json.template > /consul/config/stt-service.json
#fi

# Start the Consul agent in the background.
# This binds to the primary IP and retries joining the cluster using the hostname "consul".
#consul agent \
#  -bind=$(hostname -I | awk '{print $1}') \
#  -retry-join=consul \
#  -client=0.0.0.0 \
#  -data-dir=/consul-data \
#  -config-dir=/consul/config \
#  &

# Fix permissions for /app/output if running as root and directory exists
if [ "$(id -u)" = "0" ] && [ -d /app/output ]; then
  chown -R "${UID:-1000}:${GID:-1000}" /app/output
fi

# Give Consul a moment to initialize
sleep 2

# start vosk server
python -m app.app