# curl -X POST http://localhost:4207/embedding -H 'Content-Type: application/json' -d '{ "input": "hi my name is randi" }'

echo "              ✨ Brain embedding ✨"

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

test_case "Create embedding: /embedding" \
  "200" \
  "curl -X POST http://localhost:4207/embedding \
    -H 'Content-Type: application/json' \
    -d '{\"input\": \"test string\"}'"
