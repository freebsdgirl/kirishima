#!/bin/bash

echo "                ✨ API completions ✨"

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

test_case "Single turn: /v1/completions" \
  "200" \
  "curl -X POST http://localhost:4200/v1/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Single turn: /completions" \
  "307" \
  "curl -X POST http://localhost:4200/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Multi turn: /v1/chat/completions" \
  "200" \
  "curl -X POST http://localhost:4200/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi, how are you?\"}, {\"role\": \"assistant\", \"content\": \"I'\''m good, thank you. How about you?\"}, {\"role\": \"user\", \"content\": \"I'\''m doing great. Can you tell me a joke?\"}], \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Multi turn: /chat/completions" \
  "307" \
  "curl -X POST http://localhost:4200/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi, how are you?\"}, {\"role\": \"assistant\", \"content\": \"I'\''m good, thank you. How about you?\"}, {\"role\": \"user\", \"content\": \"I'\''m doing great. Can you tell me a joke?\"}], \"temperature\": 0.7, \"max_tokens\": 256}'"

