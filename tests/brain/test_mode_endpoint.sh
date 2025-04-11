#!/bin/bash

echo "▶ Running Brain mode tests..."

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

test_case "Getting mode: /mode" \
  "curl http://localhost:4207/mode" 
