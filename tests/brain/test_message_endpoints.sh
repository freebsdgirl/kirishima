#!/bin/bash

echo "▶ Running Brain message tests..."

test_case() {
  description="$1"
  cmd="$2"

  echo -n "→ $description "
  http_code=$(eval "$cmd" -s -o /dev/null -w "%{http_code}")
  
  if [[ "$http_code" -ge 500 ]]; then
    echo "❌ FAIL ($http_code)"
  else
    echo "✅ PASS ($http_code)"
  fi
  echo
}

test_case "Single turn: /single/incoming" \
  "curl -X POST http://localhost:4207/single/incoming \
    -H 'Content-Type: application/json' \
    -d '{\"model\": \"nemo\", \"prompt\": \"What UTC offset is PST?\", \"temperature\": 0.7, \"max_tokens\": 256}'"
