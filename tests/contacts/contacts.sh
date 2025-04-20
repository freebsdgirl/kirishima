#!/bin/bash

BASE_URL="http://localhost:4202"


echo "                                ✨ Contacts ✨"


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
# 1) CREATE a contact
# -------------------------------------------------------------------
run_and_check 200 "POST /contact (create)" \
  curl -X POST "$BASE_URL/contact" \
    -H 'Content-Type: application/json' \
    -d '{
      "notes": "Test contact notes",
      "aliases": ["alice", "al"],
      "fields": [
        {"key": "email", "value": "alice@example.com"},
        {"key": "phone", "value": "+1234567890"}
      ]
    }'

# extract and verify ID
contact_id=$(echo "$resp_body" | jq -r '.id')
if [[ -z "$contact_id" || "$contact_id" == "null" ]]; then
  echo "💀 FAIL: could not extract contact ID"
  exit 1
fi

# -------------------------------------------------------------------
# 2) GET all contacts (list)
# -------------------------------------------------------------------
run_and_check 200 "GET /contacts (list all)" \
  curl -X GET "$BASE_URL/contacts"

echo "$resp_body" | jq -e '
  (type == "array") and
  (length >= 1) and
  any(.[]; .id == "'$contact_id'")
' >/dev/null || {
  echo "   ↳ Did not return expected contact(s)                                   💀 FAIL"
  exit 1
}
echo "   ↳ GET /contacts (list all) contains new contact                       ✅ PASS"

# -------------------------------------------------------------------
# 3) SEARCH by alias
# -------------------------------------------------------------------
run_and_check 200 "GET /search?q=alice" \
  curl -X GET "$BASE_URL/search?q=alice"

echo "$resp_body" | jq -e '
  .id == "'$contact_id'" and
  (.aliases | index("alice"))
' >/dev/null || {
  echo "   ↳ Search by alias did not return expected contact                     💀 FAIL"
  exit 1
}
echo "   ↳ GET /search?q=alice returns correct contact                         ✅ PASS"

# -------------------------------------------------------------------
# 4) UPDATE contact (PUT)
# -------------------------------------------------------------------
run_and_check 200 "PUT /contact/$contact_id (replace)" \
  curl -X PUT "$BASE_URL/contact/$contact_id" \
    -H 'Content-Type: application/json' \
    -d '{
      "notes": "Updated notes",
      "aliases": ["alice2"],
      "fields": [
        {"key": "email", "value": "alice2@example.com"}
      ]
    }'

echo "$resp_body" | jq -e '
  .id == "'$contact_id'" and
  .notes == "Updated notes" and
  (.aliases | index("alice2"))
' >/dev/null || {
  echo "   ↳ PUT did not update contact as expected    💀 FAIL"
  exit 1
}
echo "   ↳ PUT /contact/$contact_id updated contact   ✅ PASS"

# -------------------------------------------------------------------
# 5) PATCH contact (partial update)
# -------------------------------------------------------------------
run_and_check 200 "PATCH /contact/$contact_id (notes, field)" \
  curl -X PATCH "$BASE_URL/contact/$contact_id" \
    -H 'Content-Type: application/json' \
    -d '{
      "notes": "Patched notes",
      "fields": [
        {"key": "twitter", "value": "@alice"}
      ]
    }'

echo "$resp_body" | jq -e '
  .id == "'$contact_id'" and
  .notes == "Patched notes" and
  any(.fields[]; .key == "twitter" and .value == "@alice")
' >/dev/null || {
  echo "   ↳ PATCH did not update contact as expected    💀 FAIL"
  exit 1
}
echo "   ↳ PATCH /contact/$contact_id patched contact ✅ PASS"

# -------------------------------------------------------------------
# 6) DELETE contact
# -------------------------------------------------------------------
run_and_check 200 "DELETE /contact/$contact_id" \
  curl -X DELETE "$BASE_URL/contact/$contact_id"

echo "$resp_body" | jq -e '.id == "'$contact_id'" and .status == "deleted"' >/dev/null || {
  echo "   ↳ DELETE did not return expected response    💀 FAIL"
  exit 1
}
echo "   ↳ DELETE /contact/$contact_id delete contact ✅ PASS"

# -------------------------------------------------------------------
# 7) VERIFY deletion: should return 404 on search
# -------------------------------------------------------------------
run_and_check 404 "GET /search?q=alice2 after delete" \
  curl -X GET "$BASE_URL/search?q=alice2"
