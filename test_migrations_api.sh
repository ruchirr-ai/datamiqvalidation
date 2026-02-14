#!/bin/bash

# Test script to check migrations API

echo "=== Testing Migrations API ==="
echo ""

# Step 1: Login to get token
echo "Step 1: Logging in as admin..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}')

echo "Login response:"
echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"
echo ""

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get access token"
  exit 1
fi

echo "Token obtained: ${TOKEN:0:20}..."
echo ""

# Step 2: List migrations
echo "Step 2: Fetching migrations list..."
MIGRATIONS_RESPONSE=$(curl -s -X GET http://localhost:8000/api/migrations/bq-redshift/list \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN")

echo "Migrations response:"
echo "$MIGRATIONS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MIGRATIONS_RESPONSE"
echo ""

# Check if response is valid JSON array
if echo "$MIGRATIONS_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Found {len(data)} migrations')" 2>/dev/null; then
  echo "✓ Migrations API is working correctly"
else
  echo "✗ Migrations API returned invalid response"
  exit 1
fi
