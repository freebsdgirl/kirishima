#!/bin/bash

echo "                   ✨ API model ✨"

test_case() {
  description="$1"
  expected_code="$2"
  cmd="$3"
  
  padding_length=40
  padded_string="$description"

  for ((i=${#description}; i<padding_length; i++)); do
    padded_string="$padded_string " # Add space to the left
  done
  echo -n "→ $padded_string"
  http_code=$(eval "$cmd" -s -o /dev/null -w "%{http_code}")
  if [[ "$http_code" -eq "$expected_code" ]]; then
    echo -n "✅ PASS ($http_code)"
  else
    echo -n "💀 FAIL (Expected $expected_code, got $http_code)"
  fi
  echo
}

test_case "List Models: /v1/models" \
  "200" \
  "curl http://localhost:4200/v1/models"

test_case "List Models: /models" \
  "307" \
  "curl http://localhost:4200/models"

test_case "Get Model: /v1/models/MODEL_NAME" \
  "200" \
  "curl http://localhost:4200/v1/models/nemo:latest"

test_case "Get Model: /models/MODEL_NAME" \
  "307" \
  "curl http://localhost:4200/models/nemo:latest"

