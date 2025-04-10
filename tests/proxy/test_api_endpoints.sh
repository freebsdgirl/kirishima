#!/bin/bash

echo "▶ Running Proxy API tests..."

test_case() {
  description="$1"
  cmd="$2"

  echo -n "→ $description "
  http_code=$(eval "$cmd" -s -o /dev/null -w "%{http_code}")
  
  if [[ "$http_code" -ge 400 ]]; then
    echo "❌ FAIL ($http_code)"
  else
    echo "✅ PASS ($http_code)"
  fi
  echo
}

test_case "Single Turn: /from/api/completions" \
  "curl -X POST http://localhost:4205/from/api/completions \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"

test_case "Multi turn: /from/api/multiturn" \
  "curl -X POST http://localhost:4205/from/api/multiturn \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"messages\": [{\"role\": \"user\", \"content\": \"Hi, how are you?\"}, {\"role\": \"assistant\", \"content\": \"I'\''m good, thank you. How about you?\"}, {\"role\": \"user\", \"content\": \"I'\''m doing great. Can you tell me a joke?\"}], \"temperature\": 0.7, \"max_tokens\": 256}'"
