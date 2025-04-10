#!/bin/bash

echo "▶ Running API completions tests..."

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

test_case "Single turn: /v1/completions" \
  "curl -X POST http://localhost:4200/v1/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Single turn: /completions" \
  "curl -X POST http://localhost:4200/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Multi turn: /v1/chat/completions" \
  "curl -X POST http://localhost:4200/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi, how are you?\"}, {\"role\": \"assistant\", \"content\": \"I'\''m good, thank you. How about you?\"}, {\"role\": \"user\", \"content\": \"I'\''m doing great. Can you tell me a joke?\"}], \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Multi turn: /chat/completions" \
  "curl -X POST http://localhost:4200/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi, how are you?\"}, {\"role\": \"assistant\", \"content\": \"I'\''m good, thank you. How about you?\"}, {\"role\": \"user\", \"content\": \"I'\''m doing great. Can you tell me a joke?\"}], \"temperature\": 0.7, \"max_tokens\": 256}'"

