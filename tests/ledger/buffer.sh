#!/bin/bash
# Test script for all user buffer endpoints in the ledger microservice
# Service base URL
BASE_URL="http://localhost:4203"
USER_ID="testuser"

# 1. POST /ledger/user/{user_id}/sync
# Sample snapshot: user sends a message, then assistant replies
cat > /tmp/snapshot1.json <<EOF
{
  "snapshot": [
    {
      "user_id": "$USER_ID",
      "platform": "api",
      "platform_msg_id": "msg-001",
      "role": "user",
      "content": "Hello, how are you?"
    },
    {
      "user_id": "$USER_ID",
      "platform": "api",
      "platform_msg_id": "msg-002",
      "role": "assistant",
      "content": "I'm good! How can I help you today?"
    }
  ]
}
EOF

echo "Posting snapshot."
echo "\nPOST /ledger/user/{user_id}/sync"
curl -s -X POST "$BASE_URL/ledger/user/$USER_ID/sync" \
  -H "Content-Type: application/json" \
  -d @/tmp/snapshot1.json | jq


echo "Getting snapshot."
# 2. GET /ledger/user/{user_id}/messages
echo "\nGET /ledger/user/{user_id}/messages"
curl -s "$BASE_URL/ledger/user/$USER_ID/messages" | jq

echo "Deleting messages prior to message_id=1."
# 3. DELETE /ledger/user/{user_id}/before/{message_id}
# (Assume message_id=1 for demo)
echo "\nDELETE /ledger/user/{user_id}/before/{message_id}"
curl -s -X DELETE "$BASE_URL/ledger/user/$USER_ID/before/1" | jq

echo "Deleting all messages from user."
# 4. DELETE /ledger/user/{user_id}
echo "\nDELETE /ledger/user/{user_id}"
curl -s -X DELETE "$BASE_URL/ledger/user/$USER_ID" | jq

# 5. GET /summaries/user/{user_id}
echo "\nGET /summaries/user/{user_id}"
curl -s "$BASE_URL/summaries/user/$USER_ID" | jq

# 6. DELETE /summaries/user/{user_id} (delete summaries with IDs 1 and 2)
cat > /tmp/delete_summaries.json <<EOF
{
  "ids": [1, 2]
}
EOF

echo "\nDELETE /summaries/user/{user_id} (with body)"
curl -s -X DELETE "$BASE_URL/summaries/user/$USER_ID" \
  -H "Content-Type: application/json" \
  -d @/tmp/delete_summaries.json | jq

# 7. POST /summaries/user/{user_id}/create
echo "\nPOST /summaries/user/{user_id}/create"
curl -s -X POST "$BASE_URL/summaries/user/$USER_ID/create" | jq

# Cleanup
echo "\nCleanup temp files"
rm -f /tmp/snapshot1.json /tmp/delete_summaries.json
