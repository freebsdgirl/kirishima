#!/bin/bash

echo "▶ Running Brain mode tests..."

test_case() {
  description="$1"
  expected_code="$2"
  cmd="$3"
  echo -n "→ $description "
  http_code=$(eval "$cmd" -s -o /dev/null -w "%{http_code}")
  if [[ "$http_code" -eq "$expected_code" ]]; then
    echo -n "✅ PASS ($http_code)"
  else
    echo -n "❌ FAIL (Expected $expected_code, got $http_code)"
  fi
  echo
}

test_case "GET /mode" \
  "200" \
  "curl http://localhost:4207/mode"

# get current mode so we can swap back to it when we test changing modes
current_mode=$(curl -s http://localhost:4207/mode | jq -r '.message')

if [[ "$current_mode" == "work" ]]; then
  target_mode="default"
else
  target_mode="work"
fi

test_case "POST mode/${target_mode}" \
  "200" \
  "curl -X POST http://localhost:4207/mode/${target_mode}"

# Setting his mode back
curl -s -X POST http://localhost:4207/mode/${current_mode} >> /dev/null
