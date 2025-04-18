#!/bin/bash

BASE_URL="http://localhost:4206"


echo "                             ✨ Chromadb memory ✨"


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
# 1) CREATE a memory entry
# -------------------------------------------------------------------
run_and_check 200 "POST /memory (create)" \
  curl -X POST "$BASE_URL/memory" \
    -H 'Content-Type: application/json' \
    -d '{
      "memory": "Test memory entry",
      "component": "proxy",
      "mode": "default",
      "priority": 0.75
    }'


# extract and verify ID
memory_id=$(echo "$resp_body" | jq -r '.id')
if [[ -z "$memory_id" || "$memory_id" == "null" ]]; then
  echo "💀 FAIL: could not extract memory ID"
  exit 1
fi

### sleep 1 second so chromadb doesn't freak tf out.
sleep 1


# -------------------------------------------------------------------
# 2) GET the memory entry by ID and verify embedding data
# -------------------------------------------------------------------
run_and_check 200 "GET /memory/id/$memory_id" \
  curl -X GET "$BASE_URL/memory/id/$memory_id"

# Validate that resp_body contains the correct fields and a numeric embedding array
echo "$resp_body" | jq -e '
  .id               == "'"$memory_id"'"          and
  .memory           == "Test memory entry"       and
  .metadata.component == "proxy"                 and
  .metadata.mode      == "default"               and
  .metadata.priority  == 0.75                    and
  (.embedding | type=="array" and length > 0)    and
  all(.embedding[]; type=="number")
' >/dev/null || {
  echo "   ↳ GET /memory body missing or invalid embedding                       💀 FAIL"
}
echo "   ↳ GET /memory response shape + embedding                              ✅ PASS"


# -------------------------------------------------------------------
# 3) LIST all memories (no filters) with embedding validation
# -------------------------------------------------------------------
run_and_check 200 "GET /memory (list all)" \
  curl -X GET "$BASE_URL/memory"

# Validate:
#  - top‑level is an array with at least one element
#  - at least one element has our memory_id
#  - every element has embedding:Array, length>0, all numbers
echo "$resp_body" | jq -e '
  (type == "array") and
  (length >= 1) and
  any(.[]; .id == "'"$memory_id"'") and
  all(.[]; (
    .embedding | type=="array" and length > 0 and all(.[]; type=="number")
  ))
' >/dev/null || {
  echo "   ↳ Did not return expected entries or valid embeddings                 💀 FAIL"
}
echo "   ↳ GET /memory (list all) + embedding                                  ✅ PASS"


# -------------------------------------------------------------------
# 4) LIST with component filter
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?component=proxy" \
  curl -X GET "$BASE_URL/memory?component=proxy"

# Validate that all returned entries have metadata.component == "proxy"
echo "$resp_body" | jq -e '
  type == "array" and
  length >= 1 and
  all(.[]; .metadata.component == "proxy")
' >/dev/null || {
  echo "   ↳ Returned items with wrong component                                 💀 FAIL"
}
echo "   ↳ GET /memory?component=proxy                                         ✅ PASS"


# -------------------------------------------------------------------
# 5) LIST with mode, priority filter & limit
# -------------------------------------------------------------------
run_and_check 200 "GET /memory?mode=default&priority=0.75&limit=1" \
  curl -X GET "$BASE_URL/memory?mode=default&priority=0.75&limit=1"

# Validate that exactly one entry is returned with the correct filters
echo "$resp_body" | jq -e '
  type == "array" and
  length == 1 and
  all(.[]; 
    .metadata.mode     == "default" and 
    .metadata.priority == 0.75
  )
' >/dev/null || {
  echo "   ↳ Did not filter correctly                                            💀 FAIL"
}
echo "   ↳ GET /memory?mode=default&priority=0.75&limit=1                      ✅ PASS"


# -------------------------------------------------------------------
# 6) SEARCH with text
# -------------------------------------------------------------------
run_and_check 404 "GET /memory/search?text=Test" \
  curl -X GET "$BASE_URL/memory/search?text=Test"


# -------------------------------------------------------------------
# 7) SEARCH with text
# -------------------------------------------------------------------
run_and_check 200 "GET /memory/search?text=Test memory entry" \
  curl -X GET "$BASE_URL/memory/search?text=Test%20memory%20entry"

# Validate that we got back at least our entry with a valid embedding
echo "$resp_body" | jq -e '
  type=="array" and
  length >= 1 and
  all(.[]; 
    .memory == "Test memory entry" and
    (.embedding | type=="array" and length > 0 and all(.[]; type=="number"))
  )
' >/dev/null || {
  echo "   ↳ Memory entry returned invalid items                                 💀 FAIL"
}
echo "   ↳ GET /memory/search?text=Test memory entry + embedding               ✅ PASS"


# -------------------------------------------------------------------
# 8) DELETE the memory entry
# -------------------------------------------------------------------
run_and_check 204 "DELETE /memory/$memory_id" \
  curl -X DELETE "$BASE_URL/memory/$memory_id"

# 9) VERIFY deletion: should return 404
run_and_check 404 "GET /memory/id/$memory_id after delete" \
  curl -X GET "$BASE_URL/memory/id/$memory_id"