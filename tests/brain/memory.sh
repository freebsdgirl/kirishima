#!/bin/bash

BASE_URL="http://localhost:4207"


echo "                               ✨ Brain memory ✨"


test_case() {
  description="$1"
  expected_code="$2"
  cmd="$3"
  
  padding_length=70
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


# -------------------------------------------------------------------
# print a padded description + PASS/FAIL like test_case
# -------------------------------------------------------------------
pad_and_print() {
  local desc="$1"
  local expected="$2"
  local actual="$3"

  # same width as test_case
  local pad_len=70
  local padded="$desc"
  for ((i=${#desc}; i<pad_len; i++)); do
    padded+=" "
  done

  # print and check
  printf "→ %s" "$padded"
  if [[ "$actual" -eq "$expected" ]]; then
    echo "✅ PASS ($actual)"
  else
    echo "💀 FAIL (Expected $expected, got $actual)"
    exit 1
  fi
}


# -------------------------------------------------------------------
# new run-and-check wrapper
# -------------------------------------------------------------------
run_and_check() {
  local expected_code="$1"
  shift
  local desc="$1"
  shift
  # run req (puts body in $resp_body, code in $resp_code)
  run_req "$@"
  # print aligned result
  pad_and_print "$desc" "$expected_code" "$resp_code"
}


# -------------------------------------------------------------------
# run a request, capturing body and HTTP code in one call
# Usage: run_req curl <args…>
# Sets globals:
#   resp_body → full response body (verbatim, including whitespace)
#   resp_code → numeric HTTP status code
# -------------------------------------------------------------------
run_req() {
  # Run curl with -sS (silent + show errors) and append "\n<status>" to the output
  local raw
  raw=$("$@" -w $'\n%{http_code}' -sS)

  # The last line after the final newline is the status code
  resp_code=${raw##*$'\n'}
  # Everything before that newline is the body
  resp_body=${raw%$'\n'*}
}

# -------------------------------------------------------------------
# 1) CREATE a memory entry via POST /memory
# -------------------------------------------------------------------
run_and_check 200 "POST /memory (create)" \
  curl -X POST "$BASE_URL/memory" \
    -H 'Content-Type: application/json' \
    -d '{
      "memory": "Brain test memory entry",
      "component": "proxy",
      "mode": "ignored-mode",
      "priority": 0.55
    }'

# extract and verify ID
memory_id=$(echo "$resp_body" | jq -r '.id')
if [[ -z "$memory_id" || "$memory_id" == "null" ]]; then
  echo "💀 FAIL: could not extract memory ID"
  exit 1
fi

sleep 1

# -------------------------------------------------------------------
# 2) LIST all memories (no filters) with embedding validation via GET /memory?component=proxy
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?component=proxy (list all)" \
  curl -X GET "$BASE_URL/memory?component=proxy"

# get the mode actually used for this memory
actual_mode=$(echo "$resp_body" | jq -r '.[] | select(.id=="'$memory_id'") | .metadata.mode')
if [[ -z "$actual_mode" || "$actual_mode" == "null" ]]; then
  echo "💀 FAIL: could not extract actual mode for created memory"
  exit 1
fi

echo "$resp_body" | jq -e '
  (type == "array") and
  (length >= 1) and
  any(.[]; .id == "'$memory_id'") and
  all(.[]; (
    .embedding | type=="array" and length > 0 and all(.[]; type=="number")
  ))
' >/dev/null || {
  echo "   ↳ Did not return expected entries or valid embeddings                  💀 FAIL"
  exit 1
}
echo "   ↳ GET /memory?component=proxy (list all) + embedding                  ✅ PASS"

# -------------------------------------------------------------------
# 3) LIST with component filter via GET /memory?component=proxy
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?component=proxy (filter)" \
  curl -X GET "$BASE_URL/memory?component=proxy"

echo "$resp_body" | jq -e '
  type == "array" and
  length >= 1 and
  all(.[]; .metadata.component == "proxy")
' >/dev/null || {
  echo "   ↳ Returned items with wrong component                                 💀 FAIL"
  exit 1
}
echo "   ↳ GET /memory?component=proxy (filter)                                ✅ PASS"

# -------------------------------------------------------------------
# 4) LIST with component, mode, priority filter & limit via GET /memory?component=proxy&mode=default&priority=0.55&limit=1
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?component=proxy&mode=$actual_mode&priority=0.55&limit=1" \
  curl -X GET "$BASE_URL/memory?component=proxy&mode=$actual_mode&priority=0.55&limit=1"

echo "$resp_body" | jq -e '
  type == "array" and
  length == 1 and
  all(.[]; 
    .metadata.component == "proxy" and
    .metadata.mode     == "'$actual_mode'" and 
    .metadata.priority == 0.55
  )
' >/dev/null || {
  echo "   ↳ Did not filter correctly                                               💀 FAIL"
  exit 1
}
echo "   ↳ GET /memory?component=proxy&mode=$actual_mode&priority=0.55&limit=1         ✅ PASS"

# -------------------------------------------------------------------
# 5) SEMANTIC SEARCH via GET /memory/semantic?component=proxy&search=Brain%20test%20memory%20entry
# -------------------------------------------------------------------
run_and_check 200 "GET /memory/semantic?component=proxy&search=Brain&mode=$actual_mode" \
  curl -X GET "$BASE_URL/memory/semantic?component=proxy&search=Brain%20test%20memory%20entry&mode=$actual_mode"

echo "$resp_body" | jq -e '
  type=="array" and
  length >= 1 and
  any(.[]; .memory == "Brain test memory entry")
' >/dev/null || {
  echo "   ↳ Semantic search did not return expected entry                        💀 FAIL"
  exit 1
}
echo "   ↳ GET /memory/semantic?component=proxy&search=Brain                   ✅ PASS"

# -------------------------------------------------------------------
# 6) DELETE memory by content/mode/component via DELETE /memory (body)
# -------------------------------------------------------------------
run_and_check 204 "DELETE /memory (by content/mode/component)" \
  curl -X DELETE "$BASE_URL/memory" \
    -H 'Content-Type: application/json' \
    -d '{
      "memory": "Brain test memory entry",
      "component": "proxy",
      "mode": "'$actual_mode'",
      "priority": 0.55
    }'

# -------------------------------------------------------------------
# 7) VERIFY deletion: should not find entry in GET /memory?component=proxy
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?component=proxy (after delete)" \
  curl -X GET "$BASE_URL/memory?component=proxy"

echo "$resp_body" | jq -e '
  all(.[]; .memory != "Brain test memory entry")
' >/dev/null || {
  echo "   ↳ Memory entry was not deleted                                        💀 FAIL"
  exit 1
}
echo "   ↳ GET /memory?component=proxy (after delete)                          ✅ PASS"

