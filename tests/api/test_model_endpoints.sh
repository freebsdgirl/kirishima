#!/bin/bash

echo "▶ Running API model tests..."

test_case() {
  description="$1"
  cmd="$2"

  echo -n "→ $description "
  http_code=$(eval "$cmd" -s -o /dev/null -w "%{http_code}")
  
  if [[ "$http_code" -ge 400 ]]; then
    echo -n "❌ FAIL ($http_code)"
  else
    echo -n "✅ PASS ($http_code)"
  fi
  echo
}

test_case "List Models: /v1/models" \
  "curl http://localhost:4200/v1/models"

test_case "List Models: /models" \
  "curl http://localhost:4200/models"

test_case "Get Model: /v1/models/MODEL_NAME" \
  "curl http://localhost:4200/v1/models/nemo:latest"

test_case "Get Model: /models/MODEL_NAME" \
  "curl http://localhost:4200/models/nemo:latest"

